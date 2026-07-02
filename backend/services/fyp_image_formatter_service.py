"""
fyp_image_formatter_service.py
================================
Drop into:  backend/services/fyp_image_formatter_service.py

Provides:
  FYPImageFormatterService   — formats ONE document's images (API-safe,
                               no sys.argv, returns structured results)
  format_fyp_document()      — thin convenience wrapper used by the router

It uses:
  • services/image_relevance.py  → generate_caption()  (BLIP already loaded)
  • python-docx + Pillow + lxml  (already in your requirements)

Nothing else needs to be installed.
"""

from __future__ import annotations

import copy
import io
import re
import os
from typing import Optional

import numpy as _np

from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image as PILImage

# ── Reuse the BLIP model that is already loaded in image_relevance.py ────────
# Import lazily so the service can be imported even before models are loaded.
def _get_caption_fn():
    try:
        from services.image_relevance import generate_caption
        return generate_caption
    except ImportError:
        try:
            from image_relevance import generate_caption
            return generate_caption
        except ImportError:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Constants  (fallbacks used when document margins cannot be read)
# ─────────────────────────────────────────────────────────────────────────────

# Safe A4 fallbacks — overridden at runtime by _read_page_geometry()
_FALLBACK_WIDTH_EMU  = 8_229_600    # ~5.71 inches
_FALLBACK_HEIGHT_EMU = 5_486_400    # ~3.81 inches (max 75 % of A4 page height)

# Image height cap as a fraction of the available page height
_MAX_HEIGHT_FRACTION = 0.75

CAPTION_FONT        = "Times New Roman"
CAPTION_SIZE_PT     = 10
CAPTION_ITALIC      = True
CAPTION_COLOR       = RGBColor(0x40, 0x40, 0x40)

SPACE_BEFORE_FIG_PT = 12   # pts before image paragraph
SPACE_AFTER_CAP_PT  = 16   # pts after caption paragraph

# Matches "Figure 1:", "Fig. 2 -", "fig3:", etc.
_CAPTION_RE = re.compile(r'^fig(?:ure)?\.?\s*\d+\s*[:\-–]?\s*', re.IGNORECASE)

_W_NS   = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WP_NS  = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A_NS   = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R_NS   = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


# ─────────────────────────────────────────────────────────────────────────────
# NEW ── Dynamic page geometry reader
# ─────────────────────────────────────────────────────────────────────────────

def _read_page_geometry(doc: Document) -> tuple[int, int]:
    """
    Read the actual page size and margins from the document's section
    properties (w:sectPr) to calculate the real usable content area.

    Returns
    -------
    (max_content_width_emu, max_content_height_emu)

    Falls back to safe A4 values if the XML is missing or malformed.
    The width is reduced by 5 % as a bleed guard so images never touch margins.
    """
    try:
        body    = doc.element.body
        sect_pr = body.find(qn('w:sectPr'))
        if sect_pr is None:
            # sectPr can live as the last child of body; try iterating
            for child in reversed(list(body)):
                if child.tag == qn('w:sectPr'):
                    sect_pr = child
                    break

        if sect_pr is None:
            raise ValueError("No w:sectPr found")

        # ── Page size ────────────────────────────────────────────────────────
        pg_sz = sect_pr.find(qn('w:pgSz'))
        if pg_sz is None:
            raise ValueError("No w:pgSz found")

        # Twips → EMU  (1 twip = 635 EMU)
        pg_w_twip = int(pg_sz.get(qn('w:w'), 12240))   # 12240 twip = 8.5 in
        pg_h_twip = int(pg_sz.get(qn('w:h'), 15840))   # 15840 twip = 11 in

        # Detect landscape orientation (w:orient="landscape" swaps w/h in sectPr)
        orient = pg_sz.get(qn('w:orient'), 'portrait')
        if orient == 'landscape':
            pg_w_twip, pg_h_twip = pg_h_twip, pg_w_twip

        # ── Page margins ──────────────────────────────────────────────────────
        pg_mar = sect_pr.find(qn('w:pgMar'))
        if pg_mar is not None:
            left   = int(pg_mar.get(qn('w:left'),   1440))
            right  = int(pg_mar.get(qn('w:right'),  1440))
            top    = int(pg_mar.get(qn('w:top'),    1440))
            bottom = int(pg_mar.get(qn('w:bottom'), 1440))
        else:
            left = right = top = bottom = 1440   # 1-inch default

        # ── Usable content area ───────────────────────────────────────────────
        usable_w_twip = pg_w_twip - left - right
        usable_h_twip = pg_h_twip - top  - bottom

        # Twips → EMU  (1 twip = 635 EMU exactly)
        usable_w_emu = int(usable_w_twip * 635)
        usable_h_emu = int(usable_h_twip * 635)

        # Apply 5 % guard band on width (prevents images touching the text column edge)
        max_w = int(usable_w_emu * 0.95)
        # Cap height at 75 % of usable page height (leaves room for caption)
        max_h = int(usable_h_emu * _MAX_HEIGHT_FRACTION)

        print(
            f"[FYPFormatter] Page geometry: "
            f"{pg_w_twip/1440:.2f}in x {pg_h_twip/1440:.2f}in "
            f"margins L{left/1440:.2f}in R{right/1440:.2f}in "
            f"usable {max_w/914400:.2f}in x {max_h/914400:.2f}in"
        )

        return max_w, max_h

    except Exception as e:
        print(f"[FYPFormatter] Could not read page geometry ({e}) — using fallback")
        return _FALLBACK_WIDTH_EMU, _FALLBACK_HEIGHT_EMU


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _emu_to_in(emu: int) -> float:
    return emu / 914_400

def _in_to_emu(inches: float) -> int:
    return int(inches * 914_400)

def _img_pixel_size(doc: Document, rId: str) -> Optional[tuple]:
    """Return (w_px, h_px) for rId, or None."""
    try:
        part = doc.part.related_parts.get(rId)
        if part:
            img = PILImage.open(io.BytesIO(part.blob))
            return img.size
    except Exception:
        pass
    return None

def _compute_display_size(
    orig_w: int,
    orig_h: int,
    px: Optional[tuple],
    max_w_emu: int = _FALLBACK_WIDTH_EMU,
    max_h_emu: int = _FALLBACK_HEIGHT_EMU,
) -> tuple[int, int]:
    """
    Fit image within the dynamically-computed page limits.
    Preserves aspect ratio. Never upscales beyond the image's natural size.

    Parameters
    ----------
    orig_w / orig_h  : current EMU extents from the document XML
    px               : (width_px, height_px) from the actual image blob, or None
    max_w_emu        : usable content width  — from _read_page_geometry()
    max_h_emu        : usable content height — from _read_page_geometry()
    """
    # If EMU extents are missing or zero, derive from pixel size
    if orig_w <= 0 or orig_h <= 0:
        if px:
            # Assume 96 dpi screen resolution as a conservative baseline
            orig_w = _in_to_emu(px[0] / 96)
            orig_h = _in_to_emu(px[1] / 96)
        else:
            return max_w_emu // 2, max_h_emu // 2

    ar = orig_h / orig_w   # height-to-width ratio

    # Step 1: cap width
    w = min(orig_w, max_w_emu)
    h = int(w * ar)

    # Step 2: if height still exceeds limit, shrink from height side
    if h > max_h_emu:
        h = max_h_emu
        w = int(h / ar)

    # Step 3: never upscale beyond the image's natural pixel resolution
    if px:
        nat_w_emu = _in_to_emu(px[0] / 96)
        nat_h_emu = _in_to_emu(px[1] / 96)
        if w > nat_w_emu and nat_w_emu > 0:
            w = nat_w_emu
            h = int(w * ar)

    return w, h

def _pPr(p_el):
    ppr = p_el.find(qn('w:pPr'))
    if ppr is None:
        ppr = OxmlElement('w:pPr')
        p_el.insert(0, ppr)
    return ppr

def _set_jc(p_el, val='center'):
    ppr = _pPr(p_el)
    jc  = ppr.find(qn('w:jc'))
    if jc is None:
        jc = OxmlElement('w:jc'); ppr.append(jc)
    jc.set(qn('w:val'), val)

def _set_spacing(p_el, before=None, after=None):
    ppr = _pPr(p_el)
    sp  = ppr.find(qn('w:spacing'))
    if sp is None:
        sp = OxmlElement('w:spacing'); ppr.append(sp)
    if before is not None:
        sp.set(qn('w:before'), str(int(before * 20)))
    if after is not None:
        sp.set(qn('w:after'), str(int(after * 20)))
    sp.set(qn('w:lineRule'), 'auto')
    sp.set(qn('w:line'), '276')

def _flag(p_el, tag: str, val: bool):
    ppr  = _pPr(p_el)
    elem = ppr.find(qn(tag))
    if val and elem is None:
        ppr.append(OxmlElement(tag))
    elif not val and elem is not None:
        ppr.remove(elem)

def _remove_page_break_before(p_el):
    _flag(p_el, 'w:pageBreakBefore', False)

def _ensure_inline(drawing_el):
    """Convert floating wp:anchor → wp:inline (In Line with Text)."""
    anchor = drawing_el.find(qn('wp:anchor'))
    if anchor is None:
        return
    existing_inline = drawing_el.find(qn('wp:inline'))
    if existing_inline is not None:
        drawing_el.remove(anchor)
        return

    inline = OxmlElement('wp:inline')
    for attr in ('distT', 'distB', 'distL', 'distR'):
        inline.set(attr, '0')
    for tag in ('wp:extent', 'wp:effectExtent', 'wp:docPr',
                'wp:cNvGraphicFramePr', 'a:graphic'):
        child = anchor.find(qn(tag))
        if child is not None:
            inline.append(copy.deepcopy(child))
    drawing_el.append(inline)
    drawing_el.remove(anchor)

def _set_extent(inline_el, w: int, h: int):
    ext = inline_el.find(qn('wp:extent'))
    if ext is None:
        ext = OxmlElement('wp:extent')
        inline_el.insert(0, ext)
    ext.set('cx', str(w)); ext.set('cy', str(h))

    # Mirror into a:graphic → pic:spPr → a:xfrm → a:ext
    try:
        ns = f"{{{_A_NS}}}"
        for xfrm in inline_el.iter(f"{ns}xfrm"):
            e = xfrm.find(f"{ns}ext")
            if e is not None:
                e.set('cx', str(w)); e.set('cy', str(h))
    except Exception:
        pass

def _get_rId(inline_el) -> Optional[str]:
    try:
        blip = inline_el.find(f".//{{{_A_NS}}}blip")
        if blip is not None:
            return blip.get(f"{{{_R_NS}}}embed")
    except Exception:
        pass
    return None

def _is_caption(para) -> bool:
    return bool(_CAPTION_RE.match(para.text.strip()))

# Namespace for Word Processing Shapes (text boxes, shapes drawn in Word)
_WPS_NS  = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
_WPG_NS  = "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
_MC_NS   = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _is_picture_drawing(inline_or_anchor) -> bool:
    """
    Return True ONLY if the drawing contains an actual embedded picture (blip).
    Text boxes (wps:txbx), grouped shapes (wpg:wgp), and empty drawing containers
    all return False — we should not caption those.
    """
    # Must have a blip embed reference to be a real picture
    blip = inline_or_anchor.find(f".//{{{_A_NS}}}blip")
    if blip is None:
        return False

    # Exclude text boxes: if the drawing has a wps:txbx element it is a shape
    txbx = inline_or_anchor.find(f".//{{{_WPS_NS}}}txbx")
    if txbx is not None:
        return False

    # Exclude grouped shapes
    wgp = inline_or_anchor.find(f".//{{{_WPG_NS}}}wgp")
    if wgp is not None:
        return False

    return True


# Word appends these suffixes to alt-text when images are pasted from clipboard.
# They are meta-noise, not part of the real description.
_WORD_ALT_SUFFIXES = (
    "description automatically generated",
    "automatically generated description",
    "image with text",
    "a screen shot",
    "a screenshot",
)

def _clean_alt_text(raw: str) -> str:
    """
    Strip Word-injected suffixes from an alt-text string.

    Word automatically appends phrases like "description automatically generated"
    (or its variants) to alt-text when images are pasted from the clipboard,
    inserted from screenshots, or when it runs its AI accessibility analysis.
    These must be removed before we use the alt-text as a caption.

    Examples
    --------
    "UI Screenshot description automatically generated"
      → "UI Screenshot"

    "A diagram of a computer hardware system description automatically generated"
      → "A diagram of a computer hardware system"

    "Architecture diagram
description automatically generated"
      → "Architecture diagram"
    """


    # Normalise newlines/tabs to spaces then collapse whitespace
    text = re.sub(r'[\r\n\t]+', ' ', raw)
    text = re.sub(r'\s{2,}', ' ', text).strip()

    # Strip any of the known Word-injected suffixes (case-insensitive)
    for suffix in _WORD_ALT_SUFFIXES:
        # Match the suffix even when separated by punctuation/whitespace
        pattern = re.compile(
            r'[\s,;\.]*' + re.escape(suffix) + r'[\s,;\.]*$',
            re.IGNORECASE
        )
        text = pattern.sub('', text).strip()

    return text.strip(' ,;.')


def _get_alt_text(inline_or_anchor) -> str:
    """
    Extract and clean the image alt-text from wp:docPr.

    Priority: 'descr' attribute (long description) → 'name' attribute.
    Skips generic auto-names like "Picture 1", "Image 2".
    Strips Word-injected suffixes like "description automatically generated".
    Returns empty string if nothing useful is found.
    """
    docPr = inline_or_anchor.find(qn("wp:docPr"))
    if docPr is None:
        return ""

    descr = _clean_alt_text(docPr.get("descr") or "")
    name  = _clean_alt_text(docPr.get("name")  or "")

    # Skip generic auto-names that carry no meaningful description
    generic = ("picture", "image", "photo", "figure", "diagram", "chart", "img")

    if descr and not any(descr.lower().startswith(g) for g in generic):
        return descr
    if name and not any(name.lower().startswith(g) for g in generic):
        return name
    return ""


def _drawings_in(p_el):
    """
    Return list of (drawing_element, inline_or_anchor) for REAL picture drawings.
    Skips text boxes, grouped shapes, and any drawing without an embedded image.
    """
    result = []
    for d in p_el.iter(qn("w:drawing")):
        il = d.find(qn("wp:inline"))
        an = d.find(qn("wp:anchor"))
        t  = il if il is not None else an
        if t is not None and _is_picture_drawing(t):
            result.append((d, t))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# NEW ── Page-flow helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_empty_para(p_el) -> bool:
    """
    Return True if a paragraph contains only whitespace (or nothing).
    Used to strip blank paragraphs immediately before an image so they
    don't create a large empty space at the bottom of a page.
    """
    text = "".join(t.text or "" for t in p_el.iter(qn("w:t"))).strip()
    has_drawing = p_el.find(f".//{qn('w:drawing')}") is not None
    return (not text) and (not has_drawing)


def _remove_preceding_empty_paras(children: list, img_index: int) -> list:
    """
    Remove blank paragraphs that appear directly before an image paragraph.
    Operates on a *copy* of the child list and returns the pruned list
    together with an updated image index.

    Rules
    -----
    * Remove at most 3 consecutive empty paragraphs before the image.
    * Never remove a paragraph that carries a heading style or a page-break.
    * Never remove the first paragraph in the document.
    """
    removed = 0
    i = img_index - 1
    to_remove = set()

    while i > 0 and removed < 3:
        p = children[i]
        if p.tag != qn("w:p"):
            break
        if not _is_empty_para(p):
            break

        # Don't remove paragraphs that have heading style or explicit page break
        ppr  = p.find(qn("w:pPr"))
        if ppr is not None:
            ps = ppr.find(qn("w:pStyle"))
            if ps is not None and "heading" in (ps.get(qn("w:val"), "")).lower():
                break
            pb = ppr.find(qn("w:pageBreakBefore"))
            if pb is not None:
                break

        # Check for <w:br w:type="page"> runs
        has_page_br = any(
            br.get(qn("w:type")) == "page"
            for br in p.iter(qn("w:br"))
        )
        if has_page_br:
            break

        to_remove.add(i)
        i -= 1
        removed += 1

    new_children = [c for j, c in enumerate(children) if j not in to_remove]
    # Recalculate the image's new index
    new_img_index = img_index - len(to_remove)
    return new_children, new_img_index


def _set_widow_orphan(p_el, value: int = 2):
    """
    Set w:widowControl on a paragraph.
    value=2 means "keep at least 2 lines together" — prevents orphaned
    single lines at the top or bottom of a page.
    """
    ppr = _pPr(p_el)
    wc  = ppr.find(qn("w:widowControl"))
    if wc is None:
        wc = OxmlElement("w:widowControl")
        ppr.append(wc)
    wc.set(qn("w:val"), str(value))


def _set_dont_add_space_between_same_style(p_el):
    """
    Suppress Word's automatic extra spacing when two paragraphs of the
    same style are adjacent.  Applied to both the image paragraph and the
    caption paragraph so the gap between them is exactly what we specify
    in w:spacing, nothing more.
    """
    ppr   = _pPr(p_el)
    ctxsp = ppr.find(qn("w:contextualSpacing"))
    if ctxsp is None:
        ctxsp = OxmlElement("w:contextualSpacing")
        ppr.append(ctxsp)
    ctxsp.set(qn("w:val"), "1")


def _ensure_caption_style_exists(doc: Document):
    """
    Guarantee the 'Caption' paragraph style exists in the document styles part.
    If it doesn't, create a minimal definition so our caption paragraphs
    render with consistent formatting even in documents that never had captions.
    """
    styles_part = doc.part.styles
    if styles_part is None:
        return

    styles_el = styles_part._element
    # Check whether Caption style already defined
    for s in styles_el.iter(qn("w:style")):
        if s.get(qn("w:styleId")) == "Caption":
            return   # already present — nothing to do

    # Build a minimal Caption style definition
    caption_style = OxmlElement("w:style")
    caption_style.set(qn("w:type"),    "paragraph")
    caption_style.set(qn("w:styleId"), "Caption")

    sname = OxmlElement("w:name"); sname.set(qn("w:val"), "caption")
    based = OxmlElement("w:basedOn"); based.set(qn("w:val"), "Normal")
    lnext = OxmlElement("w:next");   lnext.set(qn("w:val"), "Normal")

    # Run properties
    cs_rpr = OxmlElement("w:rPr")
    cs_rf  = OxmlElement("w:rFonts")
    cs_rf.set(qn("w:ascii"), CAPTION_FONT); cs_rf.set(qn("w:hAnsi"), CAPTION_FONT)
    cs_rpr.append(cs_rf)
    cs_sz  = OxmlElement("w:sz");   cs_sz.set(qn("w:val"), str(CAPTION_SIZE_PT * 2))
    cs_szc = OxmlElement("w:szCs"); cs_szc.set(qn("w:val"), str(CAPTION_SIZE_PT * 2))
    cs_rpr.append(cs_sz); cs_rpr.append(cs_szc)
    cs_i = OxmlElement("w:i"); cs_rpr.append(cs_i)
    clr  = OxmlElement("w:color")
    clr.set(qn("w:val"),
            f"{CAPTION_COLOR[0]:02X}{CAPTION_COLOR[1]:02X}{CAPTION_COLOR[2]:02X}")
    cs_rpr.append(clr)

    # Paragraph properties
    cs_ppr = OxmlElement("w:pPr")
    cs_jc  = OxmlElement("w:jc"); cs_jc.set(qn("w:val"), "center"); cs_ppr.append(cs_jc)
    cs_sp  = OxmlElement("w:spacing")
    cs_sp.set(qn("w:before"), "60")
    cs_sp.set(qn("w:after"),  str(int(SPACE_AFTER_CAP_PT * 20)))
    cs_ppr.append(cs_sp)
    cs_ppr.append(OxmlElement("w:keepLines"))

    caption_style.extend([sname, based, lnext, cs_ppr, cs_rpr])
    styles_el.append(caption_style)
    print("[FYPFormatter] Created 'Caption' paragraph style in document")


# ─────────────────────────────────────────────────────────────────────────────
# Caption paragraph builder
# ─────────────────────────────────────────────────────────────────────────────

def _make_rpr(bold: bool = False) -> OxmlElement:
    """Build a standard caption w:rPr element."""
    rpr = OxmlElement('w:rPr')
    rf  = OxmlElement('w:rFonts')
    for attr in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
        rf.set(qn(attr), CAPTION_FONT)
    rpr.append(rf)
    sz  = OxmlElement('w:sz');   sz.set(qn('w:val'), str(CAPTION_SIZE_PT * 2))
    szc = OxmlElement('w:szCs'); szc.set(qn('w:val'), str(CAPTION_SIZE_PT * 2))
    rpr.append(sz); rpr.append(szc)
    if CAPTION_ITALIC:
        rpr.append(OxmlElement('w:i'))
        rpr.append(OxmlElement('w:iCs'))
    if bold:
        rpr.append(OxmlElement('w:b'))
    clr = OxmlElement('w:color')
    clr.set(qn('w:val'),
            f"{CAPTION_COLOR[0]:02X}{CAPTION_COLOR[1]:02X}{CAPTION_COLOR[2]:02X}")
    rpr.append(clr)
    return rpr


def _build_caption_para(fig_num: int, description: str) -> OxmlElement:
    p = OxmlElement('w:p')

    ppr = OxmlElement('w:pPr')
    ps = OxmlElement('w:pStyle')
    ps.set(qn('w:val'), 'Caption')
    ppr.append(ps)

    jc = OxmlElement('w:jc')
    jc.set(qn('w:val'), 'center')
    ppr.append(jc)

    ppr.append(OxmlElement('w:keepLines'))
    p.append(ppr)

    # ── FIELD START ──
    r_begin = OxmlElement('w:r')
    fldChar = OxmlElement('w:fldChar')
    fldChar.set(qn('w:fldCharType'), 'begin')
    r_begin.append(fldChar)
    p.append(r_begin)

    # ── FIELD INSTRUCTION ──
    r_instr = OxmlElement('w:r')
    instrText = OxmlElement('w:instrText')
    instrText.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    instrText.text = ' SEQ Figure \\* ARABIC '
    r_instr.append(instrText)
    p.append(r_instr)

    # ── FIELD SEPARATOR ──
    r_sep = OxmlElement('w:r')
    fldChar_sep = OxmlElement('w:fldChar')
    fldChar_sep.set(qn('w:fldCharType'), 'separate')
    r_sep.append(fldChar_sep)
    p.append(r_sep)

    # ── FIELD RESULT (number display) ──
    r_text = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.text = str(fig_num)
    r_text.append(t)
    p.append(r_text)

    # ── FIELD END ──
    r_end = OxmlElement('w:r')
    fldChar_end = OxmlElement('w:fldChar')
    fldChar_end.set(qn('w:fldCharType'), 'end')
    r_end.append(fldChar_end)
    p.append(r_end)

    # ── "Figure " text BEFORE field ──
    r_label = OxmlElement('w:r')
    t_label = OxmlElement('w:t')
    t_label.text = "Figure "
    r_label.append(t_label)
    p.insert(1, r_label)

    # ── Colon + description ──
    r_desc = OxmlElement('w:r')
    t_desc = OxmlElement('w:t')
    t_desc.text = f": {description}"
    r_desc.append(t_desc)
    p.append(r_desc)

    return p

# ─────────────────────────────────────────────────────────────────────────────
# Table of Figures builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_tof(captions: list[str]) -> list[OxmlElement]:
    """
    Build a NATIVE Microsoft Word Table of Figures using a real TOC field.

    The output is identical to what Word generates when you click:
        References → Insert Table of Figures → Caption label: Figure

    The field instruction  TOC \\h \\z \\c "Figure"  tells Word to:
        \\h  — make entries hyperlinks (Ctrl+Click to jump)
        \\z  — hide tab/page leaders in Web Layout view
        \\c "Figure" — collect paragraphs whose caption label is "Figure"

    w:dirty="true" on the fldChar begin element causes Word to
    automatically update the TOF (fill in real page numbers, refresh
    entries) the moment the document is opened — no manual F9 needed.

    The placeholder entries we insert between fldChar separate/end are
    shown only if the field has never been updated. They are replaced
    on the first open in Word.

    Returns
    -------
    List of w:p elements to append to the document body:
        [page-break-para, heading-para, tof-field-para]
    """
    XML_NS  = "http://www.w3.org/XML/1998/namespace"
    elems   = []

    # ── 1. Page break ─────────────────────────────────────────────────────────
    pb_p = OxmlElement("w:p")
    pb_r = OxmlElement("w:r")
    pb_b = OxmlElement("w:br")
    pb_b.set(qn("w:type"), "page")
    pb_r.append(pb_b)
    pb_p.append(pb_r)
    elems.append(pb_p)

    # ── 2. "Table of Figures" heading ─────────────────────────────────────────
    h_p   = OxmlElement("w:p")
    h_ppr = OxmlElement("w:pPr")
    h_ps  = OxmlElement("w:pStyle")
    h_ps.set(qn("w:val"), "Heading1")
    h_ppr.append(h_ps)
    h_p.append(h_ppr)
    h_r = OxmlElement("w:r")
    h_t = OxmlElement("w:t")
    h_t.text = "Table of Figures"
    h_r.append(h_t)
    h_p.append(h_r)
    elems.append(h_p)
    
    # ── 3. TOC field paragraph ─────────────────────────────────────────────────
    # This is exactly the XML Word writes for a Table of Figures field.
    field_p   = OxmlElement("w:p")
    field_ppr = OxmlElement("w:pPr")

    # "Table of Figures" paragraph style (Word creates this automatically)
    field_ps = OxmlElement("w:pStyle")
    field_ps.set(qn("w:val"), "TableofFigures")
    field_ppr.append(field_ps)
    note_p = OxmlElement("w:p")
    note_r = OxmlElement("w:r")
    note_t = OxmlElement("w:t")
    note_t.text = "Note: Press Ctrl + A, then F9 to update Table of Figures"
    note_r.append(note_t)
    note_rpr = OxmlElement("w:rPr")
    note_i = OxmlElement("w:i")
    note_rpr.append(note_i)
    # Font size (optional - 10pt)
    note_sz = OxmlElement("w:sz")
    note_sz.set(qn("w:val"), "20")  # 10pt * 2
    note_rpr.append(note_sz)
    note_r.insert(0, note_rpr)
    note_p.append(note_r)
    
    elems.append(note_p)
    # Right-aligned dot-leader tab stop at the right margin
    tabs_el  = OxmlElement("w:tabs")
    tab_el   = OxmlElement("w:tab")
    tab_el.set(qn("w:val"),    "right")
    tab_el.set(qn("w:leader"), "dot")
    tab_el.set(qn("w:pos"),    "9016")   # ~6.26 in from left margin
    tabs_el.append(tab_el)
    field_ppr.append(tabs_el)
    field_p.append(field_ppr)

    def _no_proof_rpr() -> OxmlElement:
        """Run properties used on all field-control runs."""
        rpr = OxmlElement("w:rPr")
        rpr.append(OxmlElement("w:noProof"))
        return rpr

    # Run A — fldChar begin (dirty=true → Word updates on open)
    r_begin  = OxmlElement("w:r")
    r_begin.append(_no_proof_rpr())
    fc_begin = OxmlElement("w:fldChar")
    fc_begin.set(qn("w:fldCharType"), "begin")
    fc_begin.set(qn("w:updateFields"), "true") 
    r_begin.append(fc_begin)
    field_p.append(r_begin)

    # Run B — TOC field instruction
    r_instr  = OxmlElement("w:r")
    r_instr.append(_no_proof_rpr())
    instr_t  = OxmlElement("w:instrText")
    instr_t.set(f"{{{XML_NS}}}space", "preserve")
    # \\h = hyperlinks  \\z = hide in web view  \\c "Figure" = caption label
    instr_t.text = r' TOC \h \z \c "Figure" '
    r_instr.append(instr_t)
    field_p.append(r_instr)

    # Run C — fldChar separate (divides instruction from cached result)
    r_sep  = OxmlElement("w:r")
    r_sep.append(_no_proof_rpr())
    fc_sep = OxmlElement("w:fldChar")
    fc_sep.set(qn("w:fldCharType"), "separate")
    r_sep.append(fc_sep)
    field_p.append(r_sep)

    # Placeholder entries (shown before first update in Word)
    # Each entry: "Figure N: description<tab>page"
    for i, cap in enumerate(captions, start=1):
        ph_r = OxmlElement("w:r")
        # Hyperlink-style formatting matching Word's default TOF appearance
        ph_rpr = OxmlElement("w:rPr")
        ph_rs  = OxmlElement("w:rStyle")
        ph_rs.set(qn("w:val"), "Hyperlink")
        ph_rpr.append(ph_rs)
        ph_r.append(ph_rpr)
        ph_t = OxmlElement("w:t")
        ph_t.set(f"{{{XML_NS}}}space", "preserve")
        ph_t.text = f"{cap}\t{i}"   # page placeholder = figure number
        ph_r.append(ph_t)
        field_p.append(ph_r)

        # Newline between entries (except after last)
        if i < len(captions):
            br_r = OxmlElement("w:r")
            br_e = OxmlElement("w:br")
            br_r.append(br_e)
            field_p.append(br_r)

    # Run D — fldChar end
    r_end  = OxmlElement("w:r")
    r_end.append(_no_proof_rpr())
    fc_end = OxmlElement("w:fldChar")
    fc_end.set(qn("w:fldCharType"), "end")
    r_end.append(fc_end)
    field_p.append(r_end)

    elems.append(field_p)
    return elems


def _ensure_tof_style_exists(doc) -> None:
    """
    Guarantee the 'TableofFigures' paragraph style exists.
    Word creates it automatically when you insert a Table of Figures.
    We need to pre-create it so our TOF field paragraph renders correctly
    even in documents that have never had a TOF before.
    """
    styles_part = doc.part.styles
    if styles_part is None:
        return

    styles_el = styles_part._element
    for s in styles_el.iter(qn("w:style")):
        if s.get(qn("w:styleId")) == "TableofFigures":
            return   # already present

    tof_style = OxmlElement("w:style")
    tof_style.set(qn("w:type"),    "paragraph")
    tof_style.set(qn("w:styleId"), "TableofFigures")

    sname = OxmlElement("w:name"); sname.set(qn("w:val"), "table of figures")
    based = OxmlElement("w:basedOn"); based.set(qn("w:val"), "Normal")
    lnext = OxmlElement("w:next");   lnext.set(qn("w:val"), "Normal")

    ppr   = OxmlElement("w:pPr")
    tabs  = OxmlElement("w:tabs")
    tab   = OxmlElement("w:tab")
    tab.set(qn("w:val"),    "right")
    tab.set(qn("w:leader"), "dot")
    tab.set(qn("w:pos"),    "9016")
    tabs.append(tab); ppr.append(tabs)

    rpr   = OxmlElement("w:rPr")
    rf    = OxmlElement("w:rFonts")
    rf.set(qn("w:ascii"), CAPTION_FONT); rf.set(qn("w:hAnsi"), CAPTION_FONT)
    rpr.append(rf)
    sz    = OxmlElement("w:sz");   sz.set(qn("w:val"),  str(CAPTION_SIZE_PT * 2))
    szc   = OxmlElement("w:szCs"); szc.set(qn("w:val"), str(CAPTION_SIZE_PT * 2))
    rpr.append(sz); rpr.append(szc)

    tof_style.extend([sname, based, lnext, ppr, rpr])
    styles_el.append(tof_style)
    print("[FYPFormatter] Created 'TableofFigures' paragraph style")


# ─────────────────────────────────────────────────────────────────────────────
# Main service class
# ─────────────────────────────────────────────────────────────────────────────

class FYPImageFormatterService:
    """
    Applies academic-standard image formatting to a .docx document.

    Usage (from a router):
        service = FYPImageFormatterService()
        result  = service.format(input_path, output_path)
    """

    def __init__(self):
        self._gen_caption = _get_caption_fn()

    # ── Public API ────────────────────────────────────────────────────────────

    def format(self, input_path: str, output_path: str) -> dict:
        """
        Apply all 13 formatting rules and return a structured result dict.

        Returns
        -------
        {
            "success"        : bool,
            "total_images"   : int,
            "captions_added" : int,
            "tof_added"      : bool,
            "images"         : list[ImageResult],
            "manual_items"   : list[str],
            "error"          : str | None,
        }
        where ImageResult = {
            "fig_num", "rId", "orig_w_in", "orig_h_in",
            "disp_w_in", "disp_h_in", "resized", "caption"
        }
        """
        try:
            return self._run(input_path, output_path)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "total_images": 0,
                "captions_added": 0,
                "tof_added": False,
                "images": [],
                "manual_items": [],
                "error": str(exc),
            }

    # ── Private core ──────────────────────────────────────────────────────────

    def _run(self, input_path: str, output_path: str) -> dict:
        doc  = Document(input_path)
        body = doc.element.body

        # ── NEW: read actual margins + ensure Caption/TOF styles exist ─────
        max_w_emu, max_h_emu = _read_page_geometry(doc)
        _ensure_caption_style_exists(doc)
        _ensure_tof_style_exists(doc)

        all_children  = list(body.iterchildren())
        img_para_map  = {}     # child_index → [(drawing, inline)]
        manual_items  = []

        # ── Step 1: Find paragraphs that contain images ───────────────────────
        for i, elem in enumerate(all_children):
            if elem.tag != qn('w:p'):
                continue
            draws = _drawings_in(elem)
            if draws:
                img_para_map[i] = draws

        if not img_para_map:
            doc.save(output_path)
            return {
                "success": True,
                "total_images": 0,
                "captions_added": 0,
                "tof_added": False,
                "images": [],
                "manual_items": [],
                "error": None,
            }

        # ── Step 2: Collect existing caption indices to remove ────────────────
        remove_indices = set()
        for i in sorted(img_para_map):
            j = i + 1
            while j < len(all_children):
                if all_children[j].tag != qn('w:p'):
                    break
                from docx.text.paragraph import Paragraph as _P
                if _is_caption(_P(all_children[j], doc)):
                    remove_indices.add(j)
                    j += 1
                else:
                    break

        # ── Step 3: Process each image (reverse order preserves indices) ───────
        # We collect (para_index, placeholder, caption_el, image_result)
        work_items = []

        for para_i in sorted(img_para_map.keys(), reverse=True):
            p_el   = all_children[para_i]
            draws  = img_para_map[para_i]

            if len(draws) > 1:
                manual_items.append(
                    f"Paragraph at body index {para_i} has {len(draws)} images in "
                    f"one paragraph. Separate them manually for individual captions."
                )

            drawing, inline = draws[0]

            # Convert anchor → inline
            _ensure_inline(drawing)
            inline = drawing.find(qn('wp:inline'))
            if inline is None:
                manual_items.append(
                    f"Para {para_i}: could not convert to inline wrapping. "
                    f"Fix manually in Word (Format Picture → Text Wrapping → In Line)."
                )
                continue

            rId = _get_rId(inline)

            # Compute sizes — now uses document-specific margin-aware limits
            ext    = inline.find(qn('wp:extent'))
            orig_w = int(ext.get('cx', 0)) if ext is not None else 0
            orig_h = int(ext.get('cy', 0)) if ext is not None else 0
            px     = _img_pixel_size(doc, rId) if rId else None
            dw, dh = _compute_display_size(
                orig_w, orig_h, px,
                max_w_emu=max_w_emu,
                max_h_emu=max_h_emu,
            )

            _set_extent(inline, dw, dh)

            # Style the image paragraph
            _set_jc(p_el, 'center')
            _set_spacing(p_el, before=SPACE_BEFORE_FIG_PT, after=0)
            _flag(p_el, 'w:keepWithNext', True)   # image + caption stay together
            _flag(p_el, 'w:keepLines', True)
            _remove_page_break_before(p_el)
            _set_widow_orphan(p_el)                 # NEW: no orphaned image lines
            _set_dont_add_space_between_same_style(p_el)  # NEW: exact spacing

            # Extract alt-text first (highest priority for captions)
            alt_text = _get_alt_text(inline)

            # Generate description: alt-text → BLIP → placeholder
            description = self._make_caption_description(rId, doc, alt_text=alt_text)

            work_items.append({
                "para_i":      para_i,
                "description": description,
                "rId":         rId,
                "orig_w":      orig_w,
                "orig_h":      orig_h,
                "disp_w":      dw,
                "disp_h":      dh,
            })

        # ── Step 4: Assign real figure numbers and build caption elements ─────
        # Sort in document order (para_i ascending) so fig 1 is nearest the top
        sorted_work     = sorted(work_items, key=lambda x: x["para_i"])
        fig_results     = []
        final_captions  = []

        for num, item in enumerate(sorted_work, start=1):
            item["fig_num"] = num
            desc             = item["description"]
            full_caption     = f"Figure {num}: {desc}"
            item["caption"]  = full_caption
            cap_el = _build_caption_para(num, desc)
            _flag(cap_el, "w:keepLines", True)
            _set_widow_orphan(cap_el)                      # NEW: no orphaned captions
            _set_dont_add_space_between_same_style(cap_el) # NEW: exact spacing
            item["cap_el"] = cap_el
            final_captions.append(full_caption)

            fig_results.append({
                "fig_num":   num,
                "rId":       item["rId"],
                "orig_w_in": round(_emu_to_in(item["orig_w"]), 2),
                "orig_h_in": round(_emu_to_in(item["orig_h"]), 2),
                "disp_w_in": round(_emu_to_in(item["disp_w"]), 2),
                "disp_h_in": round(_emu_to_in(item["disp_h"]), 2),
                "resized":   abs(item["orig_w"] - item["disp_w"]) > 100,
                "caption":   full_caption,
            })

        # ── Step 5: Rebuild body child list with caption elements inserted ──────
        new_children = [c for i, c in enumerate(all_children)
                        if i not in remove_indices]

        # Map original para indices → positions after removals
        orig_to_new = {}
        adj = 0
        for idx in range(len(all_children)):
            if idx in remove_indices:
                adj += 1
            else:
                orig_to_new[idx] = idx - adj

        # NEW: strip empty paragraphs immediately before each image paragraph.
        # Process in reverse order so earlier removals don't shift later indices.
        for item in sorted(sorted_work, key=lambda x: x["para_i"], reverse=True):
            img_new_idx = orig_to_new.get(item["para_i"], item["para_i"])
            new_children, img_new_idx = _remove_preceding_empty_paras(
                new_children, img_new_idx
            )
            # Update orig_to_new for this item in case its index shifted
            orig_to_new[item["para_i"]] = img_new_idx

        # Insert caption elements after image paragraphs (forward order, tracking offset)
        offset = 0
        for item in sorted_work:
            new_idx = orig_to_new.get(item["para_i"], item["para_i"]) + offset
            new_children.insert(new_idx + 1, item["cap_el"])
            offset += 1

        # Reconstruct body
        sect_pr = body.find(qn("w:sectPr"))
        for child in list(body):
            body.remove(child)
        for child in new_children:
            if child.tag != qn("w:sectPr"):
                body.append(child)

        # ── Step 6: Append Table of Figures ─────────────────────────────────────
        tof_added = bool(final_captions)
        if tof_added:
            for tof_el in _build_tof(final_captions):
                if tof_el.tag != qn('w:sectPr'):
                    body.append(tof_el)

        if sect_pr is not None:
            body.append(sect_pr)

        doc.save(output_path)

        return {
            "success":            True,
            "total_images":       len(sorted_work),
            "captions_added":     len(final_captions),
            "tof_added":          tof_added,
            "images":             fig_results,
            "manual_items":       manual_items,
            "error":              None,
            # NEW: expose the computed page geometry for the API response
            "page_usable_width_in":  round(_emu_to_in(max_w_emu), 2),
            "page_usable_height_in": round(_emu_to_in(max_h_emu), 2),
        }

    # ── Caption generator ─────────────────────────────────────────────────────

    # ── Image quality checker ──────────────────────────────────────────────────

    @staticmethod
    def _image_has_content(img_bytes: bytes) -> bool:
        """
        Return True if the image contains real visual content worth captioning.
        Rejects blank/white, near-monochrome, and tiny images.
        """
        try:
            img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
            w, h = img.size
            if w < 30 or h < 30:
                return False
            arr = _np.array(img, dtype=_np.float32)
            if float(arr.std()) < 8.0:
                return False
            near_white = _np.all(arr > 235, axis=2).mean()
            if near_white > 0.97:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def _clean_blip_caption(raw: str) -> str:
        """
        Post-process a raw BLIP caption to remove garbage patterns.
        Handles: "a white sheet with the words...", repeated quotes, etc.
        """
        if not raw:
            return ""
        text = raw.strip()
        # Strip trailing repeated quotes/punctuation
        text = re.sub(r"['\".]{2,}$", "", text).strip()
        # Remove BLIP self-referential openers that describe the paper not the content
        bad_openers = [
            "a white sheet with the words",
            "a white background with the words",
            "a white paper with the words",
            "a white sheet of paper",
            "a close up of a",
            "a picture of a",
            "a photo of a",
            "an image of a",
        ]
        for opener in bad_openers:
            if text.lower().startswith(opener):
                remainder = text[len(opener):].strip().strip("'\"").strip()
                text = remainder if len(remainder) > 10 else ""
                break
        # Remove any remaining long runs of repeated quote chars
        text = re.sub(r"['\"-]{3,}", "", text)
        text = re.sub(r"\s+", " ", text).strip().rstrip(".,;:")
        # Truncate at 100 chars on a word boundary
        if len(text) > 100:
            text = text[:100].rsplit(" ", 1)[0] + "..."
        return text.capitalize() if text else ""

    # ── Caption generator ─────────────────────────────────────────────────────

    def _make_caption_description(
        self,
        rId,
        doc: Document,
        alt_text: str = "",
    ) -> str:
        """
        Generate a description-only caption (no Figure N: prefix).
        Priority: 1) alt-text from wp:docPr  2) quality-gated BLIP  3) placeholder
        """
        # Priority 1: user-supplied alt-text from Word
        if alt_text and len(alt_text.strip()) > 5:
            clean = alt_text.strip().rstrip(".").capitalize()
            print(f"[FYPFormatter] Caption from alt-text: {clean!r}")
            return clean

        # Priority 2: BLIP caption — only when image has real visual content
        if rId and self._gen_caption:
            try:
                part = doc.part.related_parts.get(rId)
                if part and self._image_has_content(part.blob):
                    import uuid as _uuid
                    tmp = os.path.join("uploads", f"_fmt_tmp_{_uuid.uuid4().hex}.png")
                    os.makedirs("uploads", exist_ok=True)
                    PILImage.open(io.BytesIO(part.blob)).save(tmp)
                    try:
                        raw = self._gen_caption(tmp)
                        clean = self._clean_blip_caption(raw)
                        if clean and len(clean) > 5:
                            print(f"[FYPFormatter] BLIP caption: {clean!r}")
                            return clean
                        print(f"[FYPFormatter] BLIP output discarded: {raw!r}")
                    finally:
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
                elif part:
                    print("[FYPFormatter] Image blank/white — skipping BLIP")
            except Exception as e:
                print(f"[FYPFormatter] BLIP caption failed: {e}")

        # Priority 3: generic placeholder
        return "[Enter descriptive title here]"


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

_service_instance: Optional[FYPImageFormatterService] = None

def get_formatter_service() -> FYPImageFormatterService:
    global _service_instance
    if _service_instance is None:
        _service_instance = FYPImageFormatterService()
    return _service_instance

def format_fyp_document(input_path: str, output_path: str) -> dict:
    """
    Module-level function — call this from the FastAPI router.
    Returns the same dict as FYPImageFormatterService.format().
    """
    return get_formatter_service().format(input_path, output_path)