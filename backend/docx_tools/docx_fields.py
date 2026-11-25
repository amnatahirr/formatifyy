"""
docx_fields.py — Microsoft Word field insertion for TOC, LOT, and LOF.

python-docx does not expose TOC/list fields natively. This module builds the
required OOXML (w:fldChar / w:instrText) so lists update via Word's
"Update Table" / "Update Field" actions.
"""

from __future__ import annotations

import re
import zlib
from typing import Any, Dict, List, Optional, Tuple

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# ── Field instruction patterns ───────────────────────────────────────────────

TOC_FIELD_RE = re.compile(r"TOC\s+\\o", re.IGNORECASE)
LOT_FIELD_RE = re.compile(r'TOC\s+\\h\s+\\z\s+\\c\s+"Table"', re.IGNORECASE)
LOF_FIELD_RE = re.compile(r'TOC\s+\\h\s+\\z\s+\\c\s+"Figure"', re.IGNORECASE)

CAPTION_TEXT_RE = re.compile(
    r"^(Table|Figure)\s+(\d+)\s*:\s*(.*)$",
    re.IGNORECASE,
)

_TOC_HEADING_RE = re.compile(r"^(table\s+of\s+contents|contents)$", re.IGNORECASE)
_LOT_HEADING_RE = re.compile(r"^list\s+of\s+tables$", re.IGNORECASE)
_LOF_HEADING_RE = re.compile(r"^list\s+of\s+figures$", re.IGNORECASE)

# Bookmark marking where report body begins (after cover + project-info pages).
# TOC / LOT / LOF must be inserted BEFORE this marker, never before the cover.
FORMATIFY_BODY_START_BOOKMARK = "_FormatifyBodyStart"

_HEADING_STYLE_RE = re.compile(r"heading\s*(\d+)", re.IGNORECASE)
_NUMBERING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
_BODY_SENTENCE_RE = re.compile(r"[.!?]\s+\S")
_MAX_TOC_HEADING_WORDS = 10
_MAX_TOC_HEADING_CHARS = 90
# Reject clause fragments wrongly promoted to headings
_INCOMPLETE_HEADING_TAIL_RE = re.compile(
    r"\b(?:are|is|was|were|be|been|being|to|of|the|a|an|and|or|for|with|by|from|"
    r"in|on|at|as|that|which|who|their|its|our|my)$",
    re.IGNORECASE,
)
# Accidental outline numbers pasted onto body prose ("6. Long paragraph…")
# "6. The processing module ..." and "1.5.1. The project also covers ..." — an
# outline / heading number left on body prose (e.g. after a false heading was
# demoted). Trailing dot required, so "1.5 million users ..." is never touched.
_LEADING_OUTLINE_NUM_RE = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3})*)\.\s+(\S.*)$")

# Image detection tags (modern DrawingML + legacy VML)
BLIP_TAG = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
VML_IMAGEDATA_TAG = "{urn:schemas-microsoft-com:vml}imagedata"
W_DRAWING_TAG = qn("w:drawing")
W_PICT_TAG = qn("w:pict")
WP_INLINE_TAG = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"
WP_ANCHOR_TAG = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor"


# ═══════════════════════════════════════════════════════════════════════════════
# LOW-LEVEL OOXML HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _text_run(text: str, *, italic: bool = False, bold: bool = False) -> OxmlElement:
    run = OxmlElement("w:r")
    if italic or bold:
        r_pr = OxmlElement("w:rPr")
        if bold:
            r_pr.append(OxmlElement("w:b"))
        if italic:
            r_pr.append(OxmlElement("w:i"))
        run.append(r_pr)
    t = OxmlElement("w:t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run.append(t)
    return run


def _append_field_runs(
    paragraph_el: OxmlElement,
    instruction: str,
    placeholder: str = "Right-click to update field.",
    *,
    mark_dirty: bool = True,
) -> None:
    """Append a complete complex Word field (begin → instr → separate → result → end)."""
    r_begin = OxmlElement("w:r")
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    if mark_dirty:
        fld_begin.set(qn("w:dirty"), "true")
    r_begin.append(fld_begin)

    r_instr = OxmlElement("w:r")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = f" {instruction.strip()} "
    r_instr.append(instr_text)

    r_sep = OxmlElement("w:r")
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r_sep.append(fld_sep)

    r_result = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = placeholder
    r_result.append(t)

    r_end = OxmlElement("w:r")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r_end.append(fld_end)

    for run_el in (r_begin, r_instr, r_sep, r_result, r_end):
        paragraph_el.append(run_el)


def _append_seq_field_runs(
    paragraph_el: OxmlElement,
    seq_name: str,
    *,
    display_number: int = 1,
) -> None:
    """Append SEQ \\* ARABIC field runs for Table/Figure numbering."""
    instruction = f"SEQ {seq_name} \\* ARABIC"
    r_begin = OxmlElement("w:r")
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    r_begin.append(fld_begin)

    r_instr = OxmlElement("w:r")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = f" {instruction} "
    r_instr.append(instr_text)

    r_sep = OxmlElement("w:r")
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r_sep.append(fld_sep)

    r_result = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = str(max(1, int(display_number)))
    r_result.append(t)

    r_end = OxmlElement("w:r")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r_end.append(fld_end)

    for run_el in (r_begin, r_instr, r_sep, r_result, r_end):
        paragraph_el.append(run_el)


def _paragraph_plain_text(p_el: OxmlElement) -> str:
    return "".join(t.text or "" for t in p_el.iter(qn("w:t"))).strip()


def _paragraph_has_field(p_el: OxmlElement, pattern: re.Pattern) -> bool:
    for instr in p_el.iter(qn("w:instrText")):
        if pattern.search(instr.text or ""):
            return True
    return False


def _body_children(doc) -> List[OxmlElement]:
    return list(doc.element.body)


def _body_index(doc, element: OxmlElement) -> int:
    return _body_children(doc).index(element)


def _insert_paragraph_before(
    doc,
    ref_element: OxmlElement,
    *,
    style_id: Optional[str] = None,
) -> Paragraph:
    new_p = OxmlElement("w:p")
    if style_id:
        p_pr = OxmlElement("w:pPr")
        p_style = OxmlElement("w:pStyle")
        p_style.set(qn("w:val"), style_id)
        p_pr.append(p_style)
        new_p.append(p_pr)
    ref_element.addprevious(new_p)
    return Paragraph(new_p, doc.element.body)


def _insert_paragraph_after(
    doc,
    ref_element: OxmlElement,
    *,
    style_id: Optional[str] = None,
) -> Paragraph:
    new_p = OxmlElement("w:p")
    if style_id:
        p_pr = OxmlElement("w:pPr")
        p_style = OxmlElement("w:pStyle")
        p_style.set(qn("w:val"), style_id)
        p_pr.append(p_style)
        new_p.append(p_pr)
    ref_element.addnext(new_p)
    return Paragraph(new_p, doc.element.body)


def ensure_update_fields_on_open(doc) -> None:
    """Set w:updateFields so Word refreshes fields when the document opens."""
    settings_el = doc.settings.element
    update = settings_el.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings_el.append(update)
    update.set(qn("w:val"), "true")


def clear_numbering_from_heading_styles(doc) -> int:
    """
    Remove auto-numbering (w:numPr) from Heading / Title style definitions.

    Student templates often link Heading 1–3 to a multilevel outline list, which
    produces '5. Table of Contents' and continues 6./7./8. onto body paragraphs.
    Formatify applies hierarchical numbers as plain text instead.
    """
    cleared = 0
    try:
        styles_root = doc.styles.element
    except Exception:
        return 0

    for style in styles_root.findall(qn("w:style")):
        style_id = (style.get(qn("w:styleId")) or "").lower()
        name_el = style.find(qn("w:name"))
        name = ((name_el.get(qn("w:val")) if name_el is not None else "") or "").lower()
        if not (
            style_id.startswith("heading")
            or name.startswith("heading")
            or style_id == "title"
            or name == "title"
        ):
            continue
        p_pr = style.find(qn("w:pPr"))
        if p_pr is None:
            continue
        num_pr = p_pr.find(qn("w:numPr"))
        if num_pr is not None:
            p_pr.remove(num_pr)
            cleared += 1
    return cleared


def _numpr_points_to_bullet(doc, num_pr: OxmlElement) -> bool:
    """True when paragraph numPr resolves to a bullet (not decimal outline)."""
    num_id_el = num_pr.find(qn("w:numId"))
    if num_id_el is None:
        return False
    try:
        num_id = num_id_el.get(qn("w:val"))
    except Exception:
        return False
    try:
        numbering = doc.part.numbering_part.numbering_definitions._numbering
    except Exception:
        return False

    abstract_id = None
    for num in numbering.findall(qn("w:num")):
        if num.get(qn("w:numId")) == num_id:
            abs_ref = num.find(qn("w:abstractNumId"))
            if abs_ref is not None:
                abstract_id = abs_ref.get(qn("w:val"))
            break
    if abstract_id is None:
        return False

    for abs_num in numbering.findall(qn("w:abstractNum")):
        if abs_num.get(qn("w:abstractNumId")) != abstract_id:
            continue
        for lvl in abs_num.findall(qn("w:lvl")):
            fmt = lvl.find(qn("w:numFmt"))
            if fmt is not None and (fmt.get(qn("w:val")) or "").lower() == "bullet":
                return True
    return False


def strip_accidental_body_outline_numbering(doc) -> Dict[str, int]:
    """
    Remove Word outline/decimal list numbering from body prose paragraphs.

    Keeps genuine bullet lists. Also strips leading '6. ' / '7. ' text prefixes
    from long Normal paragraphs (outline numbers that leaked into body text).
    """
    from docx_tools.reformatter import _set_paragraph_text_preserve_style

    stats = {"numpr_removed": 0, "text_prefixes_stripped": 0, "false_headings_demoted": 0}
    body_start = find_formatify_body_start_element(doc)

    for para in list(doc.paragraphs):
        if _paragraph_in_generated_list(para):
            continue

        text = (para.text or "").strip()
        if not text:
            continue

        is_meta = _is_meta_list_heading(text)
        # Meta list titles can sit before body-start; always clean them
        if is_meta:
            p_pr = para._element.find(qn("w:pPr"))
            num_pr = p_pr.find(qn("w:numPr")) if p_pr is not None else None
            if num_pr is not None and p_pr is not None:
                p_pr.remove(num_pr)
                stats["numpr_removed"] += 1
            cleaned = _strip_numbering_prefix(text)
            if cleaned and cleaned != text:
                _set_paragraph_text_preserve_style(para, cleaned)
                stats["text_prefixes_stripped"] += 1
            continue

        if _paragraph_is_before_body_start(doc, para, body_start):
            continue

        style_name = ((para.style.name or "") if para.style else "").lower()
        level = _heading_level_from_paragraph(para)
        is_heading = "heading" in style_name or level is not None

        # Demote false headings that are really incomplete sentences / body prose
        if is_heading and not _is_valid_toc_source_heading(text):
            _demote_paragraph_from_heading(para)
            stats["false_headings_demoted"] += 1
            style_name = ((para.style.name or "") if para.style else "").lower()
            level = _heading_level_from_paragraph(para)
            is_heading = "heading" in style_name or level is not None

        p_pr = para._element.find(qn("w:pPr"))
        num_pr = p_pr.find(qn("w:numPr")) if p_pr is not None else None

        if is_heading:
            if num_pr is not None and p_pr is not None:
                p_pr.remove(num_pr)
                stats["numpr_removed"] += 1
            continue

        # Strip non-bullet list numbering from body paragraphs
        if num_pr is not None and p_pr is not None:
            if not _numpr_points_to_bullet(doc, num_pr):
                p_pr.remove(num_pr)
                stats["numpr_removed"] += 1
                # Also drop List Paragraph style when it was only for outline nums
                if "list" in style_name:
                    try:
                        para.style = doc.styles["Normal"]
                    except Exception:
                        pass

        # Strip leading outline digits from long prose ("6. The processing module…")
        m = _LEADING_OUTLINE_NUM_RE.match(text)
        if not m:
            continue
        remainder = m.group(2).strip()
        word_count = len(remainder.split())
        # Short items may be intentional numbered lists typed as plain text
        if word_count < 8:
            continue
        _set_paragraph_text_preserve_style(para, remainder)
        stats["text_prefixes_stripped"] += 1

    return stats


def estimate_body_page_numbers(doc) -> Dict[OxmlElement, int]:
    """
    Approximate Arabic page numbers for body paragraphs (1-based from body start).

    Used as PAGEREF field results so TOC/LOF show useful pages without Word
    having updated fields yet. Word can still refresh them on open.
    """
    CHARS_PER_PAGE = 2100
    IMAGE_CHARS = 900
    TABLE_CHARS = 500

    body_start = find_formatify_body_start_element(doc)
    pages: Dict[OxmlElement, int] = {}
    page = 1
    chars_on_page = 0
    past_body = body_start is None

    for child in list(doc.element.body):
        if not past_body:
            if child is body_start or (
                child.tag == qn("w:p")
                and any(
                    bm.get(qn("w:name")) == FORMATIFY_BODY_START_BOOKMARK
                    for bm in child.iter(qn("w:bookmarkStart"))
                )
            ):
                past_body = True
                page = 1
                chars_on_page = 0
            else:
                continue

        if child.tag == qn("w:tbl"):
            chars_on_page += TABLE_CHARS
            if chars_on_page >= CHARS_PER_PAGE:
                page += 1
                chars_on_page = 0
            continue

        if child.tag != qn("w:p"):
            continue

        if _paragraph_has_page_break(child):
            # Break ends the current page; following content starts next
            pages[child] = page
            page += 1
            chars_on_page = 0
            continue

        pages[child] = page
        text_len = len(_paragraph_plain_text(child))
        chars_on_page += max(50, text_len)
        if list(child.iter(BLIP_TAG)) or list(child.iter(W_DRAWING_TAG)):
            chars_on_page += IMAGE_CHARS
        if chars_on_page >= CHARS_PER_PAGE:
            page += 1
            chars_on_page = 0

    return pages


# ═══════════════════════════════════════════════════════════════════════════════
# HEADING DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


def paragraph_has_image(para) -> bool:
    """Detect inline images including DrawingML blips and legacy VML pictures."""
    el = para._element
    if list(el.iter(BLIP_TAG)):
        return True
    if list(el.iter(W_DRAWING_TAG)) or list(el.iter(W_PICT_TAG)):
        return True
    if list(el.iter(VML_IMAGEDATA_TAG)):
        return True
    if list(el.iter(WP_INLINE_TAG)) or list(el.iter(WP_ANCHOR_TAG)):
        return True
    return False


_JUNK_CAPTION_GAP_RE = re.compile(r"^[\s.\u00a0\u2022\u00b7\-–—]*$")
_LOOSE_FIGURE_CAPTION_RE = re.compile(
    r"^Figure\s*(\d+)?\s*:\s*(.*)$",
    re.IGNORECASE,
)


def _is_junk_gap_text(text: str) -> bool:
    """True for empty / '.' / bullet-only paragraphs that sit under images."""
    return bool(_JUNK_CAPTION_GAP_RE.match((text or "").strip() or ""))


def paragraph_is_figure_caption(para) -> bool:
    """True when paragraph is a Figure caption (plain or SEQ), not an image."""
    if paragraph_has_image(para):
        return False
    text = (para.text or "").strip()
    if CAPTION_TEXT_RE.match(text) and text.lower().startswith("figure"):
        return True
    if _LOOSE_FIGURE_CAPTION_RE.match(text):
        return True
    return paragraph_has_seq_caption(para._element, "Figure")


def strip_junk_text_from_image_paragraph(para) -> bool:
    """
    Clear stray '.' / whitespace text runs inside an image paragraph.
    Leaves drawings/pictures untouched.
    """
    texts = list(para._element.iter(qn("w:t")))
    combined = "".join((t.text or "") for t in texts).strip()
    if not _is_junk_gap_text(combined):
        return False
    changed = False
    for t_el in texts:
        if t_el.text:
            t_el.text = ""
            changed = True
    return changed


def _next_body_paragraphs(doc, img_para, limit: int = 16):
    """Yield following body-level paragraphs after img_para (same parent)."""
    el = img_para._element.getnext()
    seen = 0
    while el is not None and seen < limit:
        if el.tag == qn("w:p"):
            yield Paragraph(el, img_para._parent)
            seen += 1
        el = el.getnext()


def _remove_paragraph_element(para) -> None:
    el = para._element
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _move_paragraph_after(ref_para, move_para) -> None:
    """Move move_para XML so it sits immediately after ref_para."""
    move_el = move_para._element
    if move_el.getprevious() is ref_para._element:
        return
    parent = move_el.getparent()
    if parent is not None:
        parent.remove(move_el)
    ref_para._element.addnext(move_el)


def _is_placeholder_caption_desc(desc: str | None) -> bool:
    """Old auto-filled caption text (or a looping BLIP caption) that a real description replaces."""
    text = (desc or "").strip()
    if text.rstrip(".").lower() == "illustration related to the document content":
        return True
    try:
        from docx_tools.caption_text import caption_is_degenerate
    except Exception:
        return False
    return caption_is_degenerate(text)


def attach_figure_caption_below_image(
    doc,
    img_para,
    *,
    description: str = "Illustration related to the document content.",
    preferred_caption_text: str | None = None,
    force_description: bool = False,
) -> Paragraph:
    """
    Guarantee a SEQ Figure caption is the paragraph immediately under the image.

    Handles layouts where body text (or a stray '.') sits between the picture
    and an existing 'Figure N: …' caption — moves that caption up.

    force_description=True (image was replaced): never keep the text of an
    existing caption — it described the old picture — always write the new one.

    Cover / Project Details images are never captioned (returns img_para unchanged).
    """
    if is_paragraph_in_cover_or_info(doc, img_para):
        return img_para

    strip_junk_text_from_image_paragraph(img_para)
    try:
        img_para.paragraph_format.keep_with_next = True
    except Exception:
        pass

    # Drop orphan junk paragraphs ('.') sitting right under the image.
    for nxt in list(_next_body_paragraphs(doc, img_para, limit=4)):
        if paragraph_has_image(nxt):
            break
        if paragraph_is_figure_caption(nxt):
            break
        if _is_junk_gap_text(nxt.text or ""):
            _remove_paragraph_element(nxt)
            continue
        break

    cap_para = None
    desc = (description or "").strip() or "Illustration related to the document content."

    if preferred_caption_text:
        m = _LOOSE_FIGURE_CAPTION_RE.match(preferred_caption_text.strip())
        if m and (m.group(2) or "").strip():
            desc = m.group(2).strip()
        elif ":" in preferred_caption_text:
            desc = preferred_caption_text.split(":", 1)[1].strip() or desc

    followers = list(_next_body_paragraphs(doc, img_para, limit=12))
    if followers and paragraph_is_figure_caption(followers[0]):
        cap_para = followers[0]
    else:
        for cand in followers:
            if paragraph_has_image(cand):
                break
            if paragraph_is_figure_caption(cand):
                m = _LOOSE_FIGURE_CAPTION_RE.match((cand.text or "").strip())
                if force_description:
                    pass  # old caption text belongs to the replaced picture
                elif m and (m.group(2) or "").strip():
                    if not _is_placeholder_caption_desc(m.group(2)):
                        desc = m.group(2).strip()
                else:
                    cm = CAPTION_TEXT_RE.match((cand.text or "").strip())
                    if cm and cm.group(3).strip() and not _is_placeholder_caption_desc(cm.group(3)):
                        desc = cm.group(3).strip()
                _move_paragraph_after(img_para, cand)
                cap_para = cand
                break

    if cap_para is None:
        cap_para = _insert_paragraph_after(doc, img_para._element)
        rebuild_caption_with_seq(cap_para, "Figure", desc)
    elif not paragraph_has_seq_caption(cap_para._element, "Figure"):
        m = CAPTION_TEXT_RE.match((cap_para.text or "").strip())
        if (
            not force_description
            and m
            and m.group(1).lower() == "figure"
            and not _is_placeholder_caption_desc(m.group(3))
        ):
            desc = m.group(3).strip() or desc
        rebuild_caption_with_seq(cap_para, "Figure", desc)
    elif force_description:
        rebuild_caption_with_seq(cap_para, "Figure", desc)
    elif preferred_caption_text and desc:
        rebuild_caption_with_seq(cap_para, "Figure", desc)
    elif not _is_placeholder_caption_desc(desc):
        # Existing caption is only the old placeholder -> use the real description.
        cur = (cap_para.text or "").strip()
        lm = _LOOSE_FIGURE_CAPTION_RE.match(cur)
        cur_desc = (lm.group(2) if lm else "") or ""
        if _is_placeholder_caption_desc(cur_desc):
            rebuild_caption_with_seq(cap_para, "Figure", desc)

    # Remove duplicate captions further down (same description), stop at next image.
    for cand in list(_next_body_paragraphs(doc, cap_para, limit=20)):
        if paragraph_has_image(cand):
            break
        if not paragraph_is_figure_caption(cand):
            continue
        cand_text = (cand.text or "").strip()
        cand_desc = ""
        m = _LOOSE_FIGURE_CAPTION_RE.match(cand_text)
        if m:
            cand_desc = (m.group(2) or "").strip()
        if cand_desc and desc and cand_desc.lower() == desc.lower():
            _remove_paragraph_element(cand)
        elif not cand_desc and paragraph_has_seq_caption(cand._element, "Figure"):
            _remove_paragraph_element(cand)

    return cap_para


def _paragraph_in_generated_list(para) -> bool:
    """True when paragraph belongs to a generated TOC/LOT/LOF block."""
    p_el = para._element
    if (
        _paragraph_has_field(p_el, TOC_FIELD_RE)
        or _paragraph_has_field(p_el, LOF_FIELD_RE)
        or _paragraph_has_field(p_el, LOT_FIELD_RE)
    ):
        return True
    for hl in p_el.iter(qn("w:hyperlink")):
        anchor = hl.get(qn("w:anchor"), "")
        if anchor.startswith("_Toc"):
            return True
    return False


def _extract_toc_display_text(text: str, *, include_numbering: bool = True) -> str:
    """Return heading text for TOC display, preserving hierarchical numbering."""
    cleaned = text.strip()
    match = _NUMBERING_RE.match(cleaned)
    prefix = ""
    body = cleaned
    if match:
        prefix = match.group(1)
        body = match.group(2).strip()

    if ":" in body:
        title, remainder = body.split(":", 1)
        title = title.strip()
        if len(remainder.strip().split()) >= 4:
            body = title

    words = body.split()
    if len(words) > 8:
        body = " ".join(words[:8])

    title = body.strip()
    if include_numbering and prefix:
        return f"{prefix}. {title}" if title else f"{prefix}."
    return title


def _is_valid_toc_source_heading(text: str) -> bool:
    """Strict filter — only real section headings belong in the TOC."""
    if not text or _is_meta_list_heading(text):
        return False

    words = text.split()
    if len(words) > _MAX_TOC_HEADING_WORDS or len(text) > _MAX_TOC_HEADING_CHARS:
        return False

    body = _strip_numbering_prefix(text)
    if _BODY_SENTENCE_RE.search(body):
        return False

    # Incomplete clauses ("The specific objectives of the project are")
    if _INCOMPLETE_HEADING_TAIL_RE.search(body.rstrip()):
        return False

    if "/" in body and len(body.split()) > 6:
        return False

    if ":" in text:
        _title, after = text.split(":", 1)
        if len(after.strip().split()) >= 6:
            return False

    if text.rstrip().endswith((".", "?", "!")) and len(words) > 6:
        return False

    return True


def _demote_paragraph_from_heading(para) -> None:
    """Remove outline heading styling so Word TOC fields ignore this paragraph."""
    p_pr = para._element.find(qn("w:pPr"))
    if p_pr is not None:
        for tag in (qn("w:outlineLvl"),):
            child = p_pr.find(tag)
            if child is not None:
                p_pr.remove(child)
        p_style = p_pr.find(qn("w:pStyle"))
        if p_style is not None:
            style_val = (p_style.get(qn("w:val")) or "").lower()
            if "heading" in style_val:
                p_pr.remove(p_style)
    try:
        para.style = "Normal"
    except Exception:
        pass
    for run in para.runs:
        run.bold = False
        run.italic = False


def _style_meta_list_heading(para, doc, formatting_rules: Optional[Dict[str, Any]] = None) -> None:
    """Visually style front-matter list headings without Word outline levels."""
    from docx.shared import Pt
    from docx_tools.reformatter import _set_paragraph_text_preserve_style

    _demote_paragraph_from_heading(para)

    # Never keep "5. Table of Contents" — strip outline / hierarchical prefixes
    raw = (para.text or "").strip()
    cleaned = _strip_numbering_prefix(raw)
    if cleaned and cleaned != raw:
        _set_paragraph_text_preserve_style(para, cleaned)

    # Remove Word auto-numbering (style-linked or paragraph-level)
    p_pr = para._element.get_or_add_pPr()
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is not None:
        p_pr.remove(num_pr)

    try:
        para.style = doc.styles["Title"]
    except Exception:
        try:
            para.style = doc.styles["Normal"]
        except Exception:
            pass

    size = 16
    if formatting_rules:
        size = int(formatting_rules.get("heading1_size", 16) or 16)

    if para.runs:
        run = para.runs[0]
    else:
        run = para.add_run(para.text)
    run.bold = True
    run.font.size = Pt(size)


def sanitize_document_headings_for_lists(
    doc,
    formatting_rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Normalize heading styles before list generation:
    - Front-matter list headings (TOC/LOF/LOT) use Title style (no outline level)
    - Body paragraphs wrongly marked as headings are demoted to Normal
    """
    stats = {"meta_styled": 0, "demoted": 0}
    body_start = find_formatify_body_start_element(doc)

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        raw = text
        normalized = _normalize_heading_title(raw)
        is_meta = any(
            pattern.match(raw) or pattern.match(normalized)
            for pattern in _META_TOC_HEADINGS
        )

        # TOC/LOF/LOT titles often sit BEFORE the body bookmark (lists zone).
        # Always restyle them — never leave "5. Table of Contents".
        if is_meta:
            _style_meta_list_heading(para, doc, formatting_rules)
            stats["meta_styled"] += 1
            continue

        # Leave admin cover / project-info pages untouched otherwise
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue

        level = _heading_level_from_paragraph(para)
        if level is None:
            continue

        if not _is_valid_toc_source_heading(text):
            _demote_paragraph_from_heading(para)
            stats["demoted"] += 1

    return stats


def strip_frontmatter_figure_captions(doc) -> int:
    """
    Remove any figure captions on Cover / Project Details pages.

    Cover logos must never receive 'Figure N:' captions or appear in LOF.

    IMPORTANT: never remove generated TOC/LOF/LOT entry paragraphs, and never
    treat 'Table N: …' list entries as figure captions.
    """
    body_start = find_formatify_body_start_element(doc)
    removed = 0
    for para in list(doc.paragraphs):
        if not _paragraph_is_before_body_start(doc, para, body_start):
            continue
        if paragraph_has_image(para):
            continue
        # Preserve Formatify list entries (LOT lines look like "Table 1: …")
        if _is_generated_list_entry_paragraph(para._element):
            continue
        if _is_meta_list_heading((para.text or "").strip()):
            continue

        text = (para.text or "").strip()
        is_figure_caption = (
            paragraph_is_figure_caption(para)
            or paragraph_has_seq_caption(para._element, "Figure")
        )
        # Only plain Figure captions — do NOT match Table N: via CAPTION_TEXT_RE
        if not is_figure_caption:
            m = CAPTION_TEXT_RE.match(text)
            if not m or m.group(1).lower() != "figure":
                continue

        _remove_paragraph_element(para)
        removed += 1
    return removed


def ensure_figure_captions_for_lists(doc) -> Dict[str, Any]:
    """Ensure every report-body figure has a SEQ caption (skip cover / info)."""
    added = 0
    stripped = strip_frontmatter_figure_captions(doc)
    body_start = find_formatify_body_start_element(doc)

    # Element identity (not stale indices) so inserts don't attach captions to body text.
    image_paras = [
        p
        for p in doc.paragraphs
        if paragraph_has_image(p)
        and not _paragraph_is_before_body_start(doc, p, body_start)
    ]

    # Drawings made of Word shapes (no picture file) never get a BLIP caption from
    # the image formatter; give them the nearest heading instead of the placeholder.
    from docx_tools.image_formatter import _heading_fallback_description

    all_paras = doc.paragraphs
    para_index = {p._element: i for i, p in enumerate(all_paras)}

    for para in image_paras:
        had_immediate = False
        followers = list(_next_body_paragraphs(doc, para, limit=1))
        if followers and paragraph_is_figure_caption(followers[0]):
            had_immediate = True

        heading_desc = ""
        if not list(para._element.iter(qn("a:blip"))):
            idx = para_index.get(para._element)
            if idx is not None:
                heading_desc = _heading_fallback_description(doc, idx)
        if heading_desc:
            attach_figure_caption_below_image(doc, para, description=heading_desc)
        else:
            attach_figure_caption_below_image(doc, para)
        if not had_immediate:
            added += 1

    return {
        "captions_ensured": len(image_paras),
        "captions_added": added,
        "frontmatter_captions_removed": stripped,
    }

def _heading_level_from_paragraph(para) -> Optional[int]:
    text = (para.text or "").strip()
    if not text:
        return None

    style_name = (para.style.name or "") if para.style else ""
    m = _HEADING_STYLE_RE.search(style_name)
    if m:
        return max(1, min(9, int(m.group(1))))

    p_pr = para._element.find(qn("w:pPr"))
    if p_pr is not None:
        outline = p_pr.find(qn("w:outlineLvl"))
        if outline is not None:
            try:
                return max(1, min(9, int(outline.get(qn("w:val"), "0")) + 1))
            except ValueError:
                pass
    return None


def collect_headings(doc) -> List[Dict[str, Any]]:
    """Return valid section headings that should appear in a TOC."""
    entries: List[Dict[str, Any]] = []
    body_start = find_formatify_body_start_element(doc)
    for idx, para in enumerate(doc.paragraphs):
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        if _paragraph_in_generated_list(para):
            continue
        level = _heading_level_from_paragraph(para)
        if level is None:
            continue
        text = para.text.strip()
        if not text or not _is_valid_toc_source_heading(text):
            continue
        entries.append({
            "paragraph_index": idx,
            "level": level,
            "text": _extract_toc_display_text(text),
            "raw_text": text,
            "style": para.style.name if para.style else "",
        })
    return entries


def _should_number_heading_paragraph(para, text: str) -> bool:
    """True when a paragraph is a real content heading that receives 1 / 1.1 numbering."""
    if not text or _paragraph_in_generated_list(para):
        return False
    if _is_meta_list_heading(text):
        return False
    level = _heading_level_from_paragraph(para)
    if level is None:
        return False
    # Heading 4+ — style only, never auto-numbered (avoids 3.2.1.1. Title)
    if level > 3:
        return False
    return _is_valid_toc_source_heading(text)


def apply_hierarchical_heading_numbering(doc) -> int:
    """
    Renumber valid content headings from 1 using 1, 1.1, 2, 2.1 …
    Front-matter list headings, invalid heading-styled body text, and
    Heading 4+ (style-only) are skipped. Existing H4 number prefixes are stripped.
    """
    from docx_tools.reformatter import (
        _HeadingNumberTracker,
        _format_numbered_heading,
        _set_paragraph_text_preserve_style,
        _strip_heading_number_prefix,
        _is_unnumbered_frontmatter_title,
    )

    tracker = _HeadingNumberTracker()
    updated = 0
    body_start = find_formatify_body_start_element(doc)
    for para in doc.paragraphs:
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        text = para.text.strip()
        if not text:
            continue
        level = _heading_level_from_paragraph(para)
        if level is None:
            continue
        # Abstract / Acknowledgement etc. never get a section number
        if _is_unnumbered_frontmatter_title(text):
            cleaned = _strip_heading_number_prefix(text)
            if cleaned and cleaned != text:
                _set_paragraph_text_preserve_style(para, cleaned)
                updated += 1
            continue
        if level > 3:
            # Style-only: strip any erroneous 3.2.1.1-style prefix
            cleaned = _strip_heading_number_prefix(text)
            if cleaned and cleaned != text:
                _set_paragraph_text_preserve_style(para, cleaned)
                updated += 1
            continue
        if not _should_number_heading_paragraph(para, text):
            continue
        number = tracker.next_number(level)
        desired = _format_numbered_heading(text, number)
        if text != desired:
            _set_paragraph_text_preserve_style(para, desired)
            updated += 1
    return updated


def apply_heading_styles_to_document(
    doc,
    formatting_rules: Dict[str, Any],
    required_sections: List[Any],
) -> int:
    """
    Ensure detected + inferred headings use built-in Word Heading N styles.
    Returns count of paragraphs updated.
    """
    from docx_tools.reformatter import _apply_word_heading, _detect_heading_level, _parse_section_map, parse_template_styles
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    align_map = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }

    styles = parse_template_styles(formatting_rules)
    styles.pop("_heading_numbering", None)
    styles.pop("_spacing_unit", None)
    section_map = _parse_section_map(required_sections or [])

    heading_map: Dict[int, Dict[str, Any]] = {}
    try:
        from docx_tools.heading_analysis import classify_paragraphs_for_reformat
        heading_map = classify_paragraphs_for_reformat(
            list(doc.paragraphs),
            required_sections or [],
        )
    except Exception as exc:
        print(f"[docx_fields] heading classification fallback: {exc}")

    updated = 0
    body_start = find_formatify_body_start_element(doc)
    for para_idx, para in enumerate(doc.paragraphs):
        # Never restyle admin cover / project-info pages
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        text = para.text.strip()
        if not text:
            continue
        classified = heading_map.get(para_idx)
        level = _detect_heading_level(para, text, section_map, classified)
        if level is None:
            continue
        if not _is_valid_toc_source_heading(text):
            continue
        spec = styles.get(f"heading{min(level, 3)}", styles["heading1"])
        _apply_word_heading(doc, para, level, spec, align_map)
        updated += 1
    return updated


# ═══════════════════════════════════════════════════════════════════════════════
# CAPTIONS WITH SEQ FIELDS (required for LOT / LOF)
# ═══════════════════════════════════════════════════════════════════════════════


def _set_caption_paragraph_properties(p_el: OxmlElement, *, center: bool = True) -> None:
    p_pr = p_el.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        p_el.insert(0, p_pr)

    # Captions are never headings: drop outline numbering + heading level
    for tag in ("w:numPr", "w:outlineLvl"):
        for el in list(p_pr.findall(qn(tag))):
            p_pr.remove(el)

    p_style = p_pr.find(qn("w:pStyle"))
    if p_style is None:
        p_style = OxmlElement("w:pStyle")
        p_pr.insert(0, p_style)
    p_style.set(qn("w:val"), "Caption")

    if center:
        jc = p_pr.find(qn("w:jc"))
        if jc is None:
            jc = OxmlElement("w:jc")
            p_pr.append(jc)
        jc.set(qn("w:val"), "center")


def rebuild_caption_with_seq(
    para,
    label: str,
    description: str,
    *,
    number: int | None = None,
) -> None:
    """
    Rebuild a caption paragraph using a Word SEQ field.
    label: 'Table' or 'Figure'
    description: text after the number (e.g. 'User Dataset Description')
    number: visible SEQ result (defaults to 1); pass sequential n for correct LOF/LOT text
    """
    label = label.strip().title()
    p_el = para._element

    # Preserve bookmark markers (LoT/LoF anchors) across the rewrite
    bm_starts = []
    bm_ends = []
    for child in list(p_el):
        if child.tag == qn("w:bookmarkStart"):
            bm_starts.append(child)
            p_el.remove(child)
        elif child.tag == qn("w:bookmarkEnd"):
            bm_ends.append(child)
            p_el.remove(child)
        elif child.tag != qn("w:pPr"):
            p_el.remove(child)

    _set_caption_paragraph_properties(p_el, center=True)
    p_el.append(_text_run(f"{label} "))
    _append_seq_field_runs(p_el, label, display_number=number or 1)
    suffix = description.strip()
    p_el.append(_text_run(f": {suffix}" if suffix else ":"))

    for i, el in enumerate(bm_starts):
        p_el.insert(i, el)
    for el in bm_ends:
        p_el.append(el)


def paragraph_has_seq_caption(p_el: OxmlElement, label: str) -> bool:
    text = _paragraph_plain_text(p_el).lower()
    if not text.startswith(label.lower()):
        return False
    for instr in p_el.iter(qn("w:instrText")):
        if f"SEQ {label}" in (instr.text or ""):
            return True
    return False


def upgrade_plain_caption_to_seq(para) -> bool:
    """Convert 'Table 1: Foo' plain text to SEQ-based caption. Returns True if upgraded."""
    text = para.text.strip()
    m = CAPTION_TEXT_RE.match(text)
    if not m:
        return False
    if paragraph_has_seq_caption(para._element, m.group(1).title()):
        return False
    rebuild_caption_with_seq(para, m.group(1), m.group(3))
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# FIELD DETECTION & INSERTION
# ═══════════════════════════════════════════════════════════════════════════════


def document_has_toc(doc) -> bool:
    for para in doc.paragraphs:
        if _paragraph_has_field(para._element, TOC_FIELD_RE):
            return True
    return False


def _has_static_list_entries_after_heading(doc, heading_re: re.Pattern) -> bool:
    """True when a LOF/LOT heading is followed by pre-rendered entry paragraphs."""
    heading = _find_section_heading_paragraph(doc, heading_re)
    if heading is None:
        return False
    sibling = heading._element.getnext()
    while sibling is not None and sibling.tag == qn("w:p"):
        if _is_generated_list_entry_paragraph(sibling):
            return True
        text = _paragraph_plain_text(sibling)
        if not text:
            sibling = sibling.getnext()
            continue
        break
    return False


def document_has_lot(doc) -> bool:
    for para in doc.paragraphs:
        if _paragraph_has_field(para._element, LOT_FIELD_RE):
            return True
    # Formatify may emit static LOT entries (no TOC field wrapper)
    return _has_static_list_entries_after_heading(doc, _LOT_HEADING_RE)


def document_has_lof(doc) -> bool:
    for para in doc.paragraphs:
        if _paragraph_has_field(para._element, LOF_FIELD_RE):
            return True
    return _has_static_list_entries_after_heading(doc, _LOF_HEADING_RE)

_NUMBERING_PREFIX_RE = re.compile(r"^[\d]+(?:\.[\d]+)*\.?\s+")
_META_TOC_HEADINGS = (
    _TOC_HEADING_RE,
    _LOT_HEADING_RE,
    _LOF_HEADING_RE,
)


def _strip_numbering_prefix(text: str) -> str:
    return _NUMBERING_PREFIX_RE.sub("", text.strip()).strip()


def _normalize_heading_title(text: str) -> str:
    return _strip_numbering_prefix(text).lower()


def _parse_toc_level_range(levels: str) -> Tuple[int, int]:
    cleaned = (levels or "1-3").strip().replace(" ", "")
    if "-" in cleaned:
        start, end = cleaned.split("-", 1)
        try:
            return max(1, int(start)), max(1, int(end))
        except ValueError:
            pass
    try:
        lvl = max(1, int(cleaned))
        return lvl, lvl
    except ValueError:
        return 1, 3


def _is_meta_list_heading(text: str) -> bool:
    normalized = _normalize_heading_title(text)
    return any(pattern.match(normalized) for pattern in _META_TOC_HEADINGS)


def _get_max_bookmark_id(doc) -> int:
    max_id = 0
    for el in doc.element.body.iter(qn("w:bookmarkStart")):
        try:
            max_id = max(max_id, int(el.get(qn("w:id"), "0")))
        except ValueError:
            continue
    return max_id


def find_formatify_body_start_element(doc) -> Optional[OxmlElement]:
    """
    Return the paragraph/table that starts the report body
    (after cover + project-info pages), or None if unmarked.
    """
    for bm in doc.element.body.iter(qn("w:bookmarkStart")):
        if bm.get(qn("w:name")) != FORMATIFY_BODY_START_BOOKMARK:
            continue
        parent = bm.getparent()
        while parent is not None and parent.tag not in (qn("w:p"), qn("w:tbl")):
            parent = parent.getparent()
        return parent
    return None


def ensure_formatify_body_start_bookmark(doc, *, bookmark_id: Optional[int] = None) -> OxmlElement:
    """
    Ensure the first body child carries FORMATIFY_BODY_START_BOOKMARK.
    Call on the original report *before* cover/info are prepended.
    """
    existing = find_formatify_body_start_element(doc)
    if existing is not None:
        return existing

    body = doc.element.body
    if len(body) == 0:
        para = doc.add_paragraph("")
        target = para._element
    else:
        target = body[0]
        if target.tag not in (qn("w:p"), qn("w:tbl")):
            para = doc.add_paragraph("")
            body.insert(0, para._element)
            target = para._element

    bm_id = bookmark_id if bookmark_id is not None else (_get_max_bookmark_id(doc) + 1)

    for bm in list(doc.element.body.iter(qn("w:bookmarkStart"))):
        if bm.get(qn("w:name")) != FORMATIFY_BODY_START_BOOKMARK:
            continue
        bm_id_old = bm.get(qn("w:id"))
        parent = bm.getparent()
        if parent is not None:
            parent.remove(bm)
        for bm_end in list(doc.element.body.iter(qn("w:bookmarkEnd"))):
            if bm_end.get(qn("w:id")) == bm_id_old:
                end_parent = bm_end.getparent()
                if end_parent is not None:
                    end_parent.remove(bm_end)

    bm_start = OxmlElement("w:bookmarkStart")
    bm_start.set(qn("w:id"), str(bm_id))
    bm_start.set(qn("w:name"), FORMATIFY_BODY_START_BOOKMARK)
    bm_end = OxmlElement("w:bookmarkEnd")
    bm_end.set(qn("w:id"), str(bm_id))

    if target.tag == qn("w:p"):
        target.insert(0, bm_start)
        target.append(bm_end)
    else:
        marker = OxmlElement("w:p")
        marker.append(bm_start)
        marker.append(bm_end)
        target.addprevious(marker)
        target = marker
    return target


def _lists_anchor_element(doc) -> Optional[OxmlElement]:
    """
    Element before which TOC/LOT/LOF should be placed.
    Prefer the Formatify body-start bookmark so lists sit after cover + info.
    """
    body_start = find_formatify_body_start_element(doc)
    if body_start is not None:
        return body_start
    body = doc.element.body
    return body[0] if len(body) else None


def suppress_document_from_toc(doc) -> int:
    """
    Intentionally a no-op.

    Cover / project-info pages must remain byte-identical to the admin upload.
    TOC exclusion is handled by ``_FormatifyBodyStart`` + ``_prepare_toc_entries``
    (and list arrangement), without mutating cover/info paragraph styles.
    """
    return 0


def iter_body_paragraphs(doc):
    """Yield (index, paragraph) for paragraphs at/after Formatify body start."""
    body_start = find_formatify_body_start_element(doc)
    for para_idx, para in enumerate(doc.paragraphs):
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        yield para_idx, para


def is_paragraph_in_cover_or_info(doc, para) -> bool:
    """True if paragraph sits on the prepended cover / info pages."""
    return _paragraph_is_before_body_start(
        doc, para, find_formatify_body_start_element(doc)
    )


def _element_is_before_body_start(doc, element: OxmlElement) -> bool:
    """True when a body child (paragraph or table) is on cover / project-info pages."""
    body_start = find_formatify_body_start_element(doc)
    if body_start is None or element is None:
        return False
    try:
        return _body_index(doc, element) < _body_index(doc, body_start)
    except ValueError:
        return False


def _caption_description_from_text(text: str, label: str) -> str:
    """Extract 'description' from 'Figure 1: desc' / plain text."""
    raw = (text or "").strip()
    if not raw:
        return ""
    m = CAPTION_TEXT_RE.match(raw)
    if m:
        return (m.group(3) or "").strip()
    # SEQ captions often look like 'Figure 1: desc' after plain-text join
    lower = raw.lower()
    prefix = label.lower()
    if lower.startswith(prefix):
        rest = raw[len(label):].lstrip()
        rest = re.sub(r"^\d+\s*[:.\-–—]\s*", "", rest).strip()
        return rest
    if ":" in raw:
        return raw.split(":", 1)[1].strip()
    return raw


def _ensure_bookmark_on_paragraph(para, bookmark_name: str, bookmark_id: int) -> None:
    """Add bookmark markers to a heading paragraph if not already present."""
    p_el = para._element
    for bm in p_el.iter(qn("w:bookmarkStart")):
        if bm.get(qn("w:name")) == bookmark_name:
            return

    bm_start = OxmlElement("w:bookmarkStart")
    bm_start.set(qn("w:id"), str(bookmark_id))
    bm_start.set(qn("w:name"), bookmark_name)
    bm_end = OxmlElement("w:bookmarkEnd")
    bm_end.set(qn("w:id"), str(bookmark_id))
    p_el.insert(0, bm_start)
    p_el.append(bm_end)


# ── Managed _Toc bookmark lifecycle ──────────────────────────────────────────
#
# TOC/LoF/LoT anchors are named "_Toc" + 9 digits derived deterministically
# from (kind, paragraph id), so rebuilding lists reuses the same names instead
# of minting new ones from "max id + 1" every run.

_MANAGED_TOC_NAME_RE = re.compile(r"^_Toc\d{9}$")
_W14_PARAFORMAT = "{http://schemas.microsoft.com/office/word/2010/wordml}paraId"


def _paragraph_stable_key(p_el: OxmlElement) -> str:
    """Stable per-paragraph key: w14:paraId, assigned once if absent."""
    para_id = p_el.get(_W14_PARAFORMAT)
    if not para_id:
        para_id = "%08X" % (zlib.crc32(p_el.xml.encode("utf8", "ignore")) & 0xFFFFFFFF)
        # Ensure uniqueness inside this document
        seen = {
            el.get(_W14_PARAFORMAT)
            for el in p_el.getroottree().getroot().iter(qn("w:p"))
        }
        base = para_id
        n = 1
        while para_id in seen:
            para_id = "%08X%X" % (zlib.crc32(base.encode()) & 0xFFFFFFFF, n)
            n += 1
        p_el.set(_W14_PARAFORMAT, para_id)
    return para_id


def _all_bookmark_names(doc) -> set:
    return {
        bm.get(qn("w:name"))
        for bm in doc.element.body.iter(qn("w:bookmarkStart"))
        if bm.get(qn("w:name"))
    }


def _alloc_bookmark_id(doc) -> int:
    """Unique w:id not used by any bookmarkStart/bookmarkEnd in the document."""
    used = set()
    for tag in ("w:bookmarkStart", "w:bookmarkEnd"):
        for el in doc.element.body.iter(qn(tag)):
            try:
                used.add(int(el.get(qn("w:id"), "0")))
            except (TypeError, ValueError):
                continue
    candidate = max(used, default=0) + 1
    while candidate in used:
        candidate += 1
    return candidate


def _remove_bookmark_element_pair(p_el: OxmlElement, bm_start: OxmlElement) -> None:
    """Remove a bookmarkStart and its matching bookmarkEnd (same w:id)."""
    bm_id = bm_start.get(qn("w:id"))
    for el in (bm_start,):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    if p_el is not None:
        for end in list(p_el.iter(qn("w:bookmarkEnd"))):
            if end.get(qn("w:id")) == bm_id:
                parent = end.getparent()
                if parent is not None:
                    parent.remove(end)


def get_or_create_toc_bookmark(doc, para, kind: str = "toc") -> str:
    """Return the managed _Toc bookmark name for a paragraph, creating the
    start/end pair if needed. Reuses an existing managed bookmark on the same
    paragraph; a paragraph keeps at most one managed _Toc bookmark."""
    p_el = para._element if hasattr(para, "_element") else para

    managed = [
        bm
        for bm in p_el.iter(qn("w:bookmarkStart"))
        if _MANAGED_TOC_NAME_RE.match(bm.get(qn("w:name")) or "")
    ]
    if managed:
        keep = managed[0]
        for extra in managed[1:]:
            _remove_bookmark_element_pair(p_el, extra)
        name = keep.get(qn("w:name"))
        # Repair a missing end half
        bm_id = keep.get(qn("w:id"))
        has_end = any(
            e.get(qn("w:id")) == bm_id for e in p_el.iter(qn("w:bookmarkEnd"))
        )
        if not has_end:
            end = OxmlElement("w:bookmarkEnd")
            end.set(qn("w:id"), str(bm_id))
            p_el.append(end)
        return name

    key = _paragraph_stable_key(p_el)
    taken = _all_bookmark_names(doc)
    for probe in range(1000):
        digest = zlib.crc32(f"{kind}:{key}:{probe}".encode()) % 1_000_000_000
        name = f"_Toc{digest:09d}"
        if name not in taken:
            break
    else:  # pragma: no cover - practically unreachable
        name = f"_Toc{_alloc_bookmark_id(doc):09d}"

    bm_id = _alloc_bookmark_id(doc)
    bm_start = OxmlElement("w:bookmarkStart")
    bm_start.set(qn("w:id"), str(bm_id))
    bm_start.set(qn("w:name"), name)
    bm_end = OxmlElement("w:bookmarkEnd")
    bm_end.set(qn("w:id"), str(bm_id))
    p_el.insert(0, bm_start)
    p_el.append(bm_end)
    return name


def _managed_bookmark_name(name: Optional[str]) -> bool:
    if not name:
        return False
    return bool(_MANAGED_TOC_NAME_RE.match(name)) or name in ("_Ref", "_GoBack")


def normalize_bookmarks(doc) -> Dict[str, int]:
    """Garbage-collect stale/malformed managed bookmarks.

    - Removes managed _Toc/_Ref/_GoBack bookmark pairs not referenced by any
      PAGEREF field or w:hyperlink w:anchor.
    - Deletes orphan bookmarkEnd elements; repairs bookmarkStart without end.
    - Keeps at most one managed _Toc bookmark per paragraph (prefers the
      referenced one).
    Never touches user bookmarks.
    """
    body = doc.element.body
    referenced = set()
    for instr in body.iter(qn("w:instrText")):
        for m in re.finditer(r"PAGEREF\s+(\S+)", instr.text or ""):
            referenced.add(m.group(1))
    for hl in body.iter(qn("w:hyperlink")):
        anchor = hl.get(qn("w:anchor"))
        if anchor:
            referenced.add(anchor)

    removed = repaired = 0

    # Index bookmark elements by w:id
    starts: Dict[str, OxmlElement] = {}
    start_names: Dict[str, str] = {}
    for bm in list(body.iter(qn("w:bookmarkStart"))):
        bid = bm.get(qn("w:id"))
        if bid is not None:
            starts[bid] = bm
            start_names[bid] = bm.get(qn("w:name")) or ""
    ends: Dict[str, OxmlElement] = {}
    for e in list(body.iter(qn("w:bookmarkEnd"))):
        bid = e.get(qn("w:id"))
        if bid is not None:
            ends[bid] = e

    def _drop(el):
        nonlocal removed
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
            removed += 1

    # 1) bookmarkStart without end -> repair or drop
    for bid, bm in list(starts.items()):
        if bid in ends:
            continue
        name = start_names.get(bid, "")
        if _managed_bookmark_name(name) and name not in referenced:
            _drop(bm)
            starts.pop(bid, None)
        else:
            p = bm
            while p is not None and p.tag != qn("w:p"):
                p = p.getparent()
            if p is not None:
                end = OxmlElement("w:bookmarkEnd")
                end.set(qn("w:id"), bid)
                p.append(end)
                ends[bid] = end
                repaired += 1
            else:
                _drop(bm)
                starts.pop(bid, None)

    # 2) unreferenced managed pairs -> remove both halves
    for bid, bm in list(starts.items()):
        name = start_names.get(bid, "")
        end = ends.get(bid)
        if end is None:
            continue
        if _managed_bookmark_name(name) and name not in referenced:
            _drop(bm)
            _drop(end)
            starts.pop(bid, None)
            ends.pop(bid, None)

    # 3) orphan bookmarkEnd -> delete
    for bid, e in list(ends.items()):
        if bid not in starts:
            _drop(e)
            ends.pop(bid, None)

    # 4) dedupe managed bookmarks per paragraph (keep referenced, else first)
    for p in list(body.iter(qn("w:p"))):
        bms = [
            bm
            for bm in p.iter(qn("w:bookmarkStart"))
            if _MANAGED_TOC_NAME_RE.match(bm.get(qn("w:name")) or "")
        ]
        if len(bms) <= 1:
            continue
        keep = next(
            (b for b in bms if (b.get(qn("w:name")) or "") in referenced), bms[0]
        )
        for bm in bms:
            if bm is keep:
                continue
            bid = bm.get(qn("w:id"))
            end = ends.get(bid)
            _drop(bm)
            if end is not None:
                _drop(end)
            starts.pop(bid, None)
            ends.pop(bid, None)

    return {"removed": removed, "repaired": repaired}


def _entry_text_key(text: str) -> str:
    """Normalize a list-entry line for anchor matching (strip page number)."""
    t = re.sub(r"\s+\d+\s*$", "", (text or "").strip())
    return re.sub(r"\s+", " ", t).strip().lower()


def validate_and_repair_list_anchors(doc) -> Dict[str, int]:
    """Last-line defence: every PAGEREF / w:anchor target in TOC/LoF/LoT must
    resolve to a real bookmark. Missing targets are re-created on the best
    matching caption/heading paragraph (matched by entry text)."""
    body = doc.element.body
    names = _all_bookmark_names(doc)
    body_start = find_formatify_body_start_element(doc)

    # Candidate anchor paragraphs: body paragraphs with text
    candidates = []
    for para in doc.paragraphs:
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        text = (para.text or "").strip()
        if text:
            candidates.append((_entry_text_key(text), para))

    repaired = dropped = 0
    seen_targets = set()
    for p in list(body.iter(qn("w:p"))):
        targets = []
        for instr in p.iter(qn("w:instrText")):
            targets += re.findall(r"PAGEREF\s+(\S+)", instr.text or "")
        for hl in p.iter(qn("w:hyperlink")):
            anc = hl.get(qn("w:anchor"))
            if anc:
                targets.append(anc)
        if not targets:
            continue
        entry_key = _entry_text_key(_paragraph_plain_text(p))
        for tgt in targets:
            if tgt in names or tgt in seen_targets:
                continue
            seen_targets.add(tgt)
            # find candidate whose text starts with the entry's caption part
            match = None
            probe = entry_key[:40]
            for ckey, cpara in candidates:
                if probe and (ckey.startswith(probe[:30]) or probe.startswith(ckey[:30])):
                    match = cpara
                    break
            if match is not None:
                _ensure_bookmark_on_paragraph(
                    match, tgt, _alloc_bookmark_id(doc)
                )
                names.add(tgt)
                repaired += 1
            else:
                dropped += 1
    return {"repaired": repaired, "dropped": dropped}


def repair_list_anchors_in_file(path: str) -> Dict[str, int]:
    """Open a .docx, run validate_and_repair_list_anchors, save. Returns stats."""
    from docx import Document

    doc = Document(path)
    stats = validate_and_repair_list_anchors(doc)
    doc.save(path)
    return stats


def _calculate_toc_tab_position(doc) -> int:
    """Return right-aligned tab position in twips for TOC dot leaders."""
    try:
        section = doc.sections[0]
        content_width = section.page_width - section.left_margin - section.right_margin
        twips = int(content_width / 635)
        return max(4000, twips - 120)
    except Exception:
        return 9000


def _append_pageref_field_runs(
    paragraph_el: OxmlElement,
    bookmark_name: str,
    *,
    page_number: int = 1,
) -> None:
    r_begin = OxmlElement("w:r")
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    r_begin.append(fld_begin)

    r_instr = OxmlElement("w:r")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = f" PAGEREF {bookmark_name} \\h "
    r_instr.append(instr_text)

    r_sep = OxmlElement("w:r")
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r_sep.append(fld_sep)

    r_result = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = str(max(1, int(page_number)))
    r_result.append(t)

    r_end = OxmlElement("w:r")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r_end.append(fld_end)

    for run_el in (r_begin, r_instr, r_sep, r_result, r_end):
        paragraph_el.append(run_el)


def _build_toc_entry_paragraph(
    level: int,
    text: str,
    bookmark_name: str,
    tab_pos: int,
    *,
    page_number: int = 1,
) -> OxmlElement:
    p = OxmlElement("w:p")
    p_pr = OxmlElement("w:pPr")

    # Comfortable academic list spacing (avoid congested LOF/LOT lines)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "120")
    spacing.set(qn("w:after"), "120")
    spacing.set(qn("w:line"), "360")  # 1.5 line
    spacing.set(qn("w:lineRule"), "auto")
    p_pr.append(spacing)

    if level > 1:
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), str(220 * (level - 1)))
        p_pr.append(ind)

    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:leader"), "dot")
    tab.set(qn("w:pos"), str(tab_pos))
    tabs.append(tab)
    p_pr.append(tabs)

    no_proof = OxmlElement("w:rPr")
    no_proof.append(OxmlElement("w:noProof"))
    p_pr.append(no_proof)
    p.append(p_pr)

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("w:anchor"), bookmark_name)
    hyperlink.set(qn("w:history"), "1")
    r_link = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "24")  # 12pt
    r_pr.append(sz)
    r_link.append(r_pr)
    t = OxmlElement("w:t")
    t.text = text
    r_link.append(t)
    hyperlink.append(r_link)
    p.append(hyperlink)

    r_tab = OxmlElement("w:r")
    r_tab.append(OxmlElement("w:tab"))
    p.append(r_tab)

    _append_pageref_field_runs(p, bookmark_name, page_number=page_number)
    return p


def _vanish_run_props() -> OxmlElement:
    r_pr = OxmlElement("w:rPr")
    r_pr.append(OxmlElement("w:vanish"))
    r_pr.append(OxmlElement("w:webHidden"))
    return r_pr


def _build_toc_field_start_paragraph(instruction: str) -> OxmlElement:
    """
    TOC/LOF/LOT field begin paragraph.

    Instruction text is vanished so viewers (and PDF exporters) do not show
    raw codes like: TOC \\h \\z \\c \"Figure\".
    """
    p = OxmlElement("w:p")

    r_begin = OxmlElement("w:r")
    r_begin.append(_vanish_run_props())
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    fld_begin.set(qn("w:dirty"), "true")
    r_begin.append(fld_begin)
    p.append(r_begin)

    r_instr = OxmlElement("w:r")
    r_instr.append(_vanish_run_props())
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = f" {instruction.strip()} "
    r_instr.append(instr_text)
    p.append(r_instr)

    r_sep = OxmlElement("w:r")
    r_sep.append(_vanish_run_props())
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r_sep.append(fld_sep)
    p.append(r_sep)
    return p


def _build_toc_field_end_paragraph() -> OxmlElement:
    p = OxmlElement("w:p")
    r_end = OxmlElement("w:r")
    r_end.append(_vanish_run_props())
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r_end.append(fld_end)
    p.append(r_end)
    return p


def _paragraph_is_before_body_start(doc, para, body_start: Optional[OxmlElement]) -> bool:
    """True when paragraph belongs to cover/info region (before body-start bookmark)."""
    if body_start is None:
        return False
    try:
        return _body_index(doc, para._element) < _body_index(doc, body_start)
    except ValueError:
        pass
    # Fallback: document-order walk
    for el in doc.element.body.iter():
        if el is para._element:
            return True
        if el is body_start:
            return False
        if (
            el.tag == qn("w:bookmarkStart")
            and el.get(qn("w:name")) == FORMATIFY_BODY_START_BOOKMARK
        ):
            return False
    return False


def _paragraph_is_table_or_figure_caption(para) -> bool:
    """True for caption paragraphs (Caption style, SEQ caption, or caption text)
    so they never appear in the main TOC."""
    p_el = para._element
    p_pr = p_el.find(qn("w:pPr"))
    if p_pr is not None:
        ps = p_pr.find(qn("w:pStyle"))
        if ps is not None and (ps.get(qn("w:val")) or "").lower() == "caption":
            return True
    text = (para.text or "").strip()
    if not text:
        return False
    if paragraph_has_seq_caption(p_el, "Table") or paragraph_has_seq_caption(
        p_el, "Figure"
    ):
        return True
    return bool(CAPTION_TEXT_RE.match(text))


def _prepare_toc_entries(doc, levels: str = "1-3") -> List[Dict[str, Any]]:
    """Collect TOC source headings, add bookmarks, and exclude meta list headings."""
    min_level, max_level = _parse_toc_level_range(levels)
    entries: List[Dict[str, Any]] = []
    body_start = find_formatify_body_start_element(doc)
    page_map = estimate_body_page_numbers(doc)

    for idx, para in enumerate(doc.paragraphs):
        # Never list cover / project-info page headings in the TOC
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        if _paragraph_in_generated_list(para):
            continue
        # Table/Figure captions are not headings — keep them out of the TOC
        if _paragraph_is_table_or_figure_caption(para):
            continue
        level = _heading_level_from_paragraph(para)
        if level is None or level < min_level or level > max_level:
            continue

        raw_text = para.text.strip()
        if not raw_text or not _is_valid_toc_source_heading(raw_text):
            continue

        display_text = _extract_toc_display_text(raw_text)
        bookmark_name = get_or_create_toc_bookmark(doc, para, "toc")
        entries.append({
            "paragraph_index": idx,
            "level": level,
            "text": display_text,
            "raw_text": raw_text,
            "bookmark": bookmark_name,
            "page": page_map.get(para._element, 1),
        })

    return entries


def _insert_elements_after(ref_element: OxmlElement, elements: List[OxmlElement]) -> None:
    cursor = ref_element
    for element in elements:
        cursor.addnext(element)
        cursor = element


def _is_generated_list_entry_paragraph(p_el: OxmlElement) -> bool:
    """Detect pre-rendered TOC/LOT/LOF entry paragraphs."""
    if _paragraph_has_field(p_el, TOC_FIELD_RE) or _paragraph_has_field(p_el, LOF_FIELD_RE) or _paragraph_has_field(p_el, LOT_FIELD_RE):
        return False
    has_toc_link = any(
        (hl.get(qn("w:anchor")) or "").startswith("_Toc")
        for hl in p_el.iter(qn("w:hyperlink"))
    )
    has_pageref = any(
        "PAGEREF" in (instr.text or "")
        for instr in p_el.iter(qn("w:instrText"))
    )
    return has_toc_link or has_pageref


def _remove_generated_list_entry_paragraphs(doc) -> int:
    removed = 0
    for child in list(doc.element.body):
        if child.tag != qn("w:p"):
            continue
        if _is_generated_list_entry_paragraph(child):
            parent = child.getparent()
            if parent is not None:
                parent.remove(child)
                removed += 1
    return removed


def _remove_list_field_block(doc, field_pattern: re.Pattern) -> bool:
    """
    Remove an existing list field block (single- or multi-paragraph).

    CRITICAL: must never delete past the field end into the report body.
    Older logic kept deleting until an outer end was found; if the end marker
    was missing (e.g. stripped as an 'empty' paragraph), the entire document
    after the TOC/LOF/LOT field was destroyed.
    """
    body = doc.element.body
    removed_any = False
    max_field_paras = 400

    while True:
        children = list(body)
        start_idx = None
        for i, child in enumerate(children):
            if child.tag == qn("w:p") and _paragraph_has_field(child, field_pattern):
                start_idx = i
                break
        if start_idx is None:
            break

        to_remove: List[OxmlElement] = []
        found_end = False
        for j in range(start_idx, min(len(children), start_idx + max_field_paras + 1)):
            el = children[j]
            if el.tag != qn("w:p"):
                # Tables / sectPr / drawings — stop; do not delete across them
                break

            text = _paragraph_plain_text(el)
            if (
                j > start_idx
                and text
                and _is_meta_list_heading(text)
                and not _is_generated_list_entry_paragraph(el)
                and not _paragraph_has_field(el, field_pattern)
            ):
                # Next TOC/LOF/LOT heading — keep it
                break

            # Body content that is clearly not a list entry — stop before it
            if (
                j > start_idx
                and text
                and not _is_generated_list_entry_paragraph(el)
                and not _paragraph_has_word_field_marks(el)
                and not _paragraph_has_field(el, field_pattern)
                and len(text) > 80
            ):
                break

            to_remove.append(el)

            # Single-paragraph field (begin+end together)
            if (
                j == start_idx
                and _paragraph_has_field_begin(el)
                and _paragraph_has_field_end(el)
            ):
                found_end = True
                break
            if _paragraph_is_outer_list_field_end(el, field_pattern):
                found_end = True
                break

        if not found_end:
            # Missing end marker: only remove field-related paragraphs, never body
            safe: List[OxmlElement] = []
            for el in to_remove:
                if (
                    _paragraph_has_field(el, field_pattern)
                    or _paragraph_has_word_field_marks(el)
                    or _is_generated_list_entry_paragraph(el)
                ):
                    safe.append(el)
                elif not _paragraph_plain_text(el).strip():
                    # blank line inside the field block
                    safe.append(el)
                else:
                    break
            to_remove = safe if safe else to_remove[:1]

        if not to_remove:
            break

        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
                removed_any = True

    return removed_any


def _cleanup_all_list_artifacts(doc) -> Dict[str, int]:
    """Remove every existing TOC/LOT/LOF field block and orphan entry paragraphs."""
    removed = {"toc": 0, "lot": 0, "lof": 0, "orphans": 0}
    while _remove_list_field_block(doc, TOC_FIELD_RE):
        removed["toc"] += 1
    while _remove_list_field_block(doc, LOF_FIELD_RE):
        removed["lof"] += 1
    while _remove_list_field_block(doc, LOT_FIELD_RE):
        removed["lot"] += 1
    removed["orphans"] = _remove_generated_list_entry_paragraphs(doc)
    return removed


def _remove_static_list_entries_after_heading(doc, heading_re: re.Pattern) -> bool:
    """Remove pre-rendered LOF/LOT entry paragraphs under a list heading."""
    heading = _find_section_heading_paragraph(doc, heading_re)
    if heading is None:
        return False
    removed = False
    sibling = heading._element.getnext()
    while sibling is not None and sibling.tag == qn("w:p"):
        nxt = sibling.getnext()
        text = _paragraph_plain_text(sibling)
        if _is_generated_list_entry_paragraph(sibling):
            parent = sibling.getparent()
            if parent is not None:
                parent.remove(sibling)
                removed = True
            sibling = nxt
            continue
        if not text.strip():
            # Drop blank lines sandwiched between heading and leftover entries
            parent = sibling.getparent()
            if parent is not None:
                parent.remove(sibling)
                removed = True
            sibling = nxt
            continue
        break
    return removed


def _remove_toc_field_block(doc) -> bool:
    return _remove_list_field_block(doc, TOC_FIELD_RE)


def _remove_lof_field_block(doc) -> bool:
    removed = _remove_list_field_block(doc, LOF_FIELD_RE)
    removed = _remove_static_list_entries_after_heading(doc, _LOF_HEADING_RE) or removed
    return removed


def _remove_lot_field_block(doc) -> bool:
    removed = _remove_list_field_block(doc, LOT_FIELD_RE)
    removed = _remove_static_list_entries_after_heading(doc, _LOT_HEADING_RE) or removed
    return removed


def _list_field_is_unpopulated(doc, field_pattern: re.Pattern, empty_markers: tuple[str, ...]) -> bool:
    for para in doc.paragraphs:
        if not _paragraph_has_field(para._element, field_pattern):
            continue
        text = para.text.strip().lower()
        if any(marker in text for marker in empty_markers):
            return True
    return False


def _toc_field_is_unpopulated(doc) -> bool:
    return _list_field_is_unpopulated(
        doc,
        TOC_FIELD_RE,
        ("right-click", "update field", "no table of contents entries"),
    )


def _lof_field_is_unpopulated(doc) -> bool:
    if _has_static_list_entries_after_heading(doc, _LOF_HEADING_RE):
        return False
    return _list_field_is_unpopulated(
        doc,
        LOF_FIELD_RE,
        ("right-click", "update field", "no table of figures entries"),
    )


def _lot_field_is_unpopulated(doc) -> bool:
    if _has_static_list_entries_after_heading(doc, _LOT_HEADING_RE):
        return False
    return _list_field_is_unpopulated(
        doc,
        LOT_FIELD_RE,
        ("right-click", "update field", "no table of tables entries"),
    )


def _prepare_lof_entries(doc) -> List[Dict[str, Any]]:
    """Collect figure captions from the REPORT BODY only (skip cover / info)."""
    entries: List[Dict[str, Any]] = []
    body_start = find_formatify_body_start_element(doc)

    ensure_figure_captions_for_lists(doc)
    page_map = estimate_body_page_numbers(doc)

    figure_number = 0
    for idx, para in enumerate(doc.paragraphs):
        # Cover logo + any project-info images are never listed
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        if not paragraph_has_image(para):
            continue

        cap_para = None
        cap_text = ""
        if idx + 1 < len(doc.paragraphs):
            nxt = doc.paragraphs[idx + 1]
            if _paragraph_is_before_body_start(doc, nxt, body_start):
                continue
            nxt_text = nxt.text.strip()
            if (
                not paragraph_has_image(nxt)
                and (
                    CAPTION_TEXT_RE.match(nxt_text)
                    or paragraph_has_seq_caption(nxt._element, "Figure")
                )
            ):
                cap_para = nxt
                cap_text = nxt_text

        if cap_para is None:
            continue

        figure_number += 1
        description = _caption_description_from_text(cap_text, "Figure")
        if not description:
            description = "Illustration related to the document content."

        # Always renumber sequentially so LOF does not show Figure 1 for every item
        rebuild_caption_with_seq(
            cap_para, "Figure", description, number=figure_number
        )

        bookmark_name = get_or_create_toc_bookmark(doc, cap_para, "lof")
        display = f"Figure {figure_number}: {description}"
        entries.append({
            "paragraph_index": idx,
            "level": 1,
            "text": display,
            "bookmark": bookmark_name,
            "page": page_map.get(cap_para._element, page_map.get(para._element, 1)),
        })

    return entries


def _prepare_lot_entries(
    doc,
    formatting_rules: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Collect table captions from the REPORT BODY only (skip cover / info tables)."""
    from services.table_caption_service import find_caption_near_table
    from services.table_config import format_table_caption_label, get_table_format_config
    from services.table_numbering_service import (
        apply_numbering_to_table_captions,
        assign_table_numbers,
    )

    cfg = get_table_format_config(formatting_rules)
    assignments = assign_table_numbers(doc, formatting_rules)
    applied = apply_numbering_to_table_captions(doc, assignments, formatting_rules)
    by_id = {a["table_id"]: a for a in applied}

    entries: List[Dict[str, Any]] = []
    page_map = estimate_body_page_numbers(doc)
    list_pattern = cfg.get("list_of_tables_format") or cfg.get(
        "table_caption_format_pattern"
    )

    tbl_i = 0
    for table in doc.tables:
        if _element_is_before_body_start(doc, table._tbl):
            continue
        table_id = f"tbl{tbl_i}"
        tbl_i += 1
        a = by_id.get(table_id, {})

        cap_para, _pos, raw = find_caption_near_table(doc, table)
        if cap_para is None:
            continue

        description = a.get("caption_description") or _caption_description_from_text(
            raw or (cap_para.text or ""), "Table"
        )

        n = int(a["n"]) if a.get("n") is not None else tbl_i
        chapter = a.get("chapter")
        if a.get("scheme") == "global" or chapter is None:
            rebuild_caption_with_seq(
                cap_para, "Table", description, number=n
            )

        bookmark_name = get_or_create_toc_bookmark(doc, cap_para, "lot")
        display = format_table_caption_label(
            pattern=list_pattern,
            n=n,
            chapter=chapter,
            description=description,
        )
        entries.append({
            "paragraph_index": _body_index(doc, table._tbl),
            "level": 1,
            "text": display,
            "bookmark": bookmark_name,
            "page": page_map.get(cap_para._element, 1),
        })

    return entries


def _insert_populated_list_block(
    doc,
    after_element: OxmlElement,
    instruction: str,
    entries: List[Dict[str, Any]],
    *,
    wrap_in_field: bool = True,
) -> None:
    """
    Insert list entries after a heading.

    wrap_in_field=False (LOF/LOT): static entries only — avoids visible junk like
    `TOC \\h \\z \\c "Figure"` in viewers that render instrText as body text.
    """
    tab_pos = _calculate_toc_tab_position(doc)
    elements: List[OxmlElement] = []
    if wrap_in_field:
        elements.append(_build_toc_field_start_paragraph(instruction))
    for entry in entries:
        elements.append(
            _build_toc_entry_paragraph(
                entry["level"],
                entry["text"],
                entry["bookmark"],
                tab_pos,
                page_number=int(entry.get("page") or 1),
            )
        )
    if wrap_in_field:
        elements.append(_build_toc_field_end_paragraph())
    _insert_elements_after(after_element, elements)

def _find_section_heading_paragraph(doc, pattern: re.Pattern) -> Optional[Paragraph]:
    for para in doc.paragraphs:
        raw = para.text.strip()
        normalized = _normalize_heading_title(raw)
        if pattern.match(raw) or pattern.match(normalized):
            return para
    return None


def _is_placeholder_paragraph(para) -> bool:
    text = para.text.strip().lower()
    if not text:
        return True
    return "right-click" in text or "update field" in text or "update table" in text


def _insert_field_after_heading(
    doc,
    heading_para: Optional[Paragraph],
    instruction: str,
    *,
    fallback_title: str,
    heading_level: int = 1,
) -> Paragraph:
    """Insert a Word list field after a section heading, or create the heading first."""
    from docx_tools.docx_styles import force_heading_style

    if heading_para is None:
        body = doc.element.body
        first = _lists_anchor_element(doc)
        if first is not None:
            heading_para = _insert_paragraph_before(doc, first)
        else:
            heading_para = doc.add_paragraph()
        heading_para.add_run(fallback_title)
        force_heading_style(heading_para, doc, heading_level)

    next_idx = _body_index(doc, heading_para._element) + 1
    children = _body_children(doc)
    if next_idx < len(children) and children[next_idx].tag == qn("w:p"):
        candidate = Paragraph(children[next_idx], doc.element.body)
        if _is_placeholder_paragraph(candidate) or not candidate.text.strip():
            for child in list(candidate._element):
                if child.tag != qn("w:pPr"):
                    candidate._element.remove(child)
            _append_field_runs(candidate._element, instruction)
            return candidate

    field_para = _insert_paragraph_after(doc, heading_para._element)
    _append_field_runs(field_para._element, instruction)
    return field_para


def insert_toc_field(
    doc,
    levels: str = "1-3",
    *,
    heading_para: Optional[Paragraph] = None,
    entries: Optional[List[Dict[str, Any]]] = None,
) -> Paragraph:
    """Insert a populated TOC field that renders heading entries immediately in Word."""

    instruction = f'TOC \\o "{levels}" \\h \\z \\u'
    toc_entries = entries if entries is not None else _prepare_toc_entries(doc, levels)

    if heading_para is None:
        first = _lists_anchor_element(doc)
        if first is not None:
            heading_para = _insert_paragraph_before(doc, first)
        else:
            heading_para = doc.add_paragraph()
        heading_para.add_run("Table of Contents")
        _style_meta_list_heading(heading_para, doc)

    _insert_populated_list_block(doc, heading_para._element, instruction, toc_entries)
    return heading_para


def insert_lot_field(
    doc,
    *,
    heading_para: Optional[Paragraph] = None,
    entries: Optional[List[Dict[str, Any]]] = None,
) -> Paragraph:
    instruction = 'TOC \\h \\z \\c "Table"'
    lot_entries = entries if entries is not None else _prepare_lot_entries(doc)

    if heading_para is None:
        heading_para = _find_section_heading_paragraph(doc, _LOT_HEADING_RE)
    if heading_para is None:
        first = _lists_anchor_element(doc)
        if first is not None:
            heading_para = _insert_paragraph_before(doc, first)
        else:
            heading_para = doc.add_paragraph()
        heading_para.add_run("List of Tables")
        _style_meta_list_heading(heading_para, doc)

    _insert_populated_list_block(
        doc,
        heading_para._element,
        instruction,
        lot_entries,
        wrap_in_field=False,
    )
    return heading_para


def insert_lof_field(
    doc,
    *,
    heading_para: Optional[Paragraph] = None,
    entries: Optional[List[Dict[str, Any]]] = None,
) -> Paragraph:
    instruction = 'TOC \\h \\z \\c "Figure"'
    lof_entries = entries if entries is not None else _prepare_lof_entries(doc)

    if heading_para is None:
        heading_para = _find_section_heading_paragraph(doc, _LOF_HEADING_RE)
    if heading_para is None:
        first = _lists_anchor_element(doc)
        if first is not None:
            heading_para = _insert_paragraph_before(doc, first)
        else:
            heading_para = doc.add_paragraph()
        heading_para.add_run("List of Figures")
        _style_meta_list_heading(heading_para, doc)

    _insert_populated_list_block(
        doc,
        heading_para._element,
        instruction,
        lof_entries,
        wrap_in_field=False,
    )
    return heading_para

def apply_toc_heading_styles(doc, formatting_rules: Optional[Dict[str, Any]] = None) -> int:
    """Style front-matter list headings without adding them to the TOC outline."""
    stats = sanitize_document_headings_for_lists(doc, formatting_rules)
    return stats.get("meta_styled", 0)


# ═══════════════════════════════════════════════════════════════════════════════
# FRONT-MATTER LAYOUT (TOC first, LOF/LOT on separate pages)
# ═══════════════════════════════════════════════════════════════════════════════

_FRONT_MATTER_SECTIONS: Tuple[Tuple[str, re.Pattern, re.Pattern], ...] = (
    ("toc", _TOC_HEADING_RE, TOC_FIELD_RE),
    ("lof", _LOF_HEADING_RE, LOF_FIELD_RE),
    ("lot", _LOT_HEADING_RE, LOT_FIELD_RE),
)


def _paragraph_has_field_end(p_el: OxmlElement) -> bool:
    for fld in p_el.iter(qn("w:fldChar")):
        if fld.get(qn("w:fldCharType")) == "end":
            return True
    return False


def _paragraph_has_field_begin(p_el: OxmlElement) -> bool:
    for fld in p_el.iter(qn("w:fldChar")):
        if fld.get(qn("w:fldCharType")) == "begin":
            return True
    return False


def _paragraph_is_outer_list_field_end(p_el: OxmlElement, field_re: re.Pattern) -> bool:
    """
    True only for the dedicated closing paragraph of a populated list field.
    TOC entry lines contain nested PAGEREF fields with their own begin/end nodes.
    """
    if not _paragraph_has_field_end(p_el):
        return False
    if _paragraph_has_field_begin(p_el):
        return False
    if _paragraph_has_field(p_el, field_re):
        return False
    for instr in p_el.iter(qn("w:instrText")):
        if "PAGEREF" in (instr.text or ""):
            return False
    return True


def _paragraph_has_page_break(p_el: OxmlElement) -> bool:
    for br in p_el.iter(qn("w:br")):
        if br.get(qn("w:type")) == "page":
            return True
    return False


def _build_page_break_paragraph() -> OxmlElement:
    p = OxmlElement("w:p")
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    r.append(br)
    p.append(r)
    return p


def _is_other_meta_list_heading(text: str, current_heading_re: re.Pattern) -> bool:
    if not text or not _is_meta_list_heading(text):
        return False
    normalized = _normalize_heading_title(text)
    if current_heading_re.match(text) or current_heading_re.match(normalized):
        return False
    return True


def _extract_list_section_block(
    doc,
    heading_re: re.Pattern,
    field_re: re.Pattern,
) -> Optional[List[OxmlElement]]:
    """Return heading + populated field/static entry block for one front-matter list."""
    heading_para = _find_section_heading_paragraph(doc, heading_re)
    if heading_para is None:
        return None

    elements: List[OxmlElement] = [heading_para._element]
    sibling = heading_para._element.getnext()
    saw_field = False
    max_paras = 400

    while sibling is not None and sibling.tag == qn("w:p") and len(elements) <= max_paras:
        text = _paragraph_plain_text(sibling)
        if text and _is_other_meta_list_heading(text, heading_re):
            break
        # Static lists: stop before body content (not a generated entry)
        if (
            not saw_field
            and text
            and not _is_generated_list_entry_paragraph(sibling)
            and not _paragraph_has_word_field_marks(sibling)
            and not _paragraph_has_field(sibling, field_re)
        ):
            break
        # Do not swallow the report body when field end is missing
        if (
            saw_field
            and text
            and not _is_generated_list_entry_paragraph(sibling)
            and not _paragraph_has_word_field_marks(sibling)
            and not _paragraph_has_field(sibling, field_re)
            and len(text) > 80
        ):
            break

        elements.append(sibling)
        if _paragraph_has_field(sibling, field_re):
            saw_field = True
        if saw_field and _paragraph_is_outer_list_field_end(sibling, field_re):
            return elements
        if (
            saw_field
            and _paragraph_has_field(sibling, field_re)
            and _paragraph_has_field_begin(sibling)
            and _paragraph_has_field_end(sibling)
        ):
            return elements
        sibling = sibling.getnext()

    if not saw_field:
        # Static Formatify LOF/LOT (entries without TOC field wrapper)
        static = [elements[0]]
        for el in elements[1:]:
            if _is_generated_list_entry_paragraph(el):
                static.append(el)
            elif not _paragraph_plain_text(el).strip():
                if len(static) > 1:
                    static.append(el)
                else:
                    break
            else:
                break
        return static if any(_is_generated_list_entry_paragraph(e) for e in static) else None

    # Missing end: keep only heading + field-related paragraphs
    trimmed = [elements[0]]
    for el in elements[1:]:
        if (
            _paragraph_has_field(el, field_re)
            or _paragraph_has_word_field_marks(el)
            or _is_generated_list_entry_paragraph(el)
            or not _paragraph_plain_text(el).strip()
        ):
            trimmed.append(el)
        else:
            break
    return trimmed if len(trimmed) > 1 else None


def _detach_body_elements(elements: List[OxmlElement]) -> None:
    for el in elements:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)


def _insert_elements_before(
    ref_element: Optional[OxmlElement],
    elements: List[OxmlElement],
    *,
    body: OxmlElement,
) -> None:
    for el in elements:
        if ref_element is not None:
            ref_element.addprevious(el)
        else:
            body.append(el)


def _is_page_break_only_paragraph(p_el: OxmlElement) -> bool:
    if _paragraph_plain_text(p_el).strip():
        return False
    return _paragraph_has_page_break(p_el)


def repair_formatify_body_start_bookmark(doc, *, expected_leading_page_breaks: int = 2) -> bool:
    """
    If cover/info were prepended without a bookmark, place one after the leading
    page-break paragraphs (cover page-break + info page-break).
    """
    if find_formatify_body_start_element(doc) is not None:
        return False

    breaks_seen = 0
    for child in list(doc.element.body):
        if child.tag != qn("w:p"):
            continue
        if not _is_page_break_only_paragraph(child):
            continue
        breaks_seen += 1
        if breaks_seen < expected_leading_page_breaks:
            continue
        nxt = child.getnext()
        while nxt is not None and nxt.tag == qn("w:p") and _is_page_break_only_paragraph(nxt):
            nxt = nxt.getnext()
        if nxt is None:
            return False
        bm_id = _get_max_bookmark_id(doc) + 1
        bm_start = OxmlElement("w:bookmarkStart")
        bm_start.set(qn("w:id"), str(bm_id))
        bm_start.set(qn("w:name"), FORMATIFY_BODY_START_BOOKMARK)
        bm_end = OxmlElement("w:bookmarkEnd")
        bm_end.set(qn("w:id"), str(bm_id))
        if nxt.tag == qn("w:p"):
            nxt.insert(0, bm_start)
            nxt.append(bm_end)
        else:
            marker = OxmlElement("w:p")
            marker.append(bm_start)
            marker.append(bm_end)
            nxt.addprevious(marker)
        return True
    return False


def _paragraph_is_list_entry_paragraph(p_el: OxmlElement) -> bool:
    for hl in p_el.iter(qn("w:hyperlink")):
        if (hl.get(qn("w:anchor")) or "").startswith("_Toc"):
            return True
    for instr in p_el.iter(qn("w:instrText")):
        if "PAGEREF" in (instr.text or ""):
            return True
    return False


def _count_entries_in_list_block(block: List[OxmlElement]) -> int:
    return sum(
        1
        for el in block
        if el.tag == qn("w:p") and _paragraph_is_list_entry_paragraph(el)
    )


def _front_matter_section_is_active(
    doc,
    key: str,
    heading_re: re.Pattern,
    field_re: re.Pattern,
    include_flag: bool,
) -> bool:
    """True only when a list section exists, is populated, and has at least one entry."""
    if not include_flag:
        return False

    has_field = {
        "toc": document_has_toc,
        "lof": document_has_lof,
        "lot": document_has_lot,
    }[key](doc)
    if not has_field:
        return False

    is_unpopulated = {
        "toc": _toc_field_is_unpopulated,
        "lof": _lof_field_is_unpopulated,
        "lot": _lot_field_is_unpopulated,
    }[key](doc)
    if is_unpopulated:
        return False

    block = _extract_list_section_block(doc, heading_re, field_re)
    if not block:
        return False
    return _count_entries_in_list_block(block) > 0


def _remove_meta_list_heading_paragraphs(doc, heading_re: re.Pattern) -> int:
    """Remove standalone front-matter headings that no longer have a list field."""
    removed = 0
    for para in list(doc.paragraphs):
        raw = para.text.strip()
        normalized = _normalize_heading_title(raw)
        if not (heading_re.match(raw) or heading_re.match(normalized)):
            continue

        for neighbor in (para._element.getprevious(), para._element.getnext()):
            if neighbor is None or neighbor.tag != qn("w:p"):
                continue
            if _is_page_break_only_paragraph(neighbor):
                parent = neighbor.getparent()
                if parent is not None:
                    parent.remove(neighbor)

        parent = para._element.getparent()
        if parent is not None:
            parent.remove(para._element)
            removed += 1
    return removed


def _collapse_consecutive_page_breaks(doc) -> int:
    """Remove duplicate page-break-only paragraphs that would create blank pages."""
    removed = 0
    prev_was_page_break = False
    for child in list(_body_children(doc)):
        if child.tag != qn("w:p"):
            prev_was_page_break = False
            continue
        is_page_break = _is_page_break_only_paragraph(child)
        if is_page_break and prev_was_page_break:
            parent = child.getparent()
            if parent is not None:
                parent.remove(child)
                removed += 1
            continue
        prev_was_page_break = is_page_break
    return removed


def _paragraph_has_word_field_marks(p_el: OxmlElement) -> bool:
    """True when paragraph participates in a Word complex field."""
    return bool(list(p_el.iter(qn("w:fldChar"))) or list(p_el.iter(qn("w:instrText"))))


def _paragraph_is_visually_empty(p_el: OxmlElement) -> bool:
    """True when a paragraph has no visible text/media/fields (safe to drop)."""
    if _paragraph_plain_text(p_el).strip():
        return False
    # NEVER treat TOC/LOF/LOT field begin/end markers as empty — deleting them
    # causes later list cleanup to wipe the rest of the document.
    if _paragraph_has_word_field_marks(p_el):
        return False
    if list(p_el.iter(BLIP_TAG)) or list(p_el.iter(W_DRAWING_TAG)) or list(p_el.iter(W_PICT_TAG)):
        return False
    if list(p_el.iter(VML_IMAGEDATA_TAG)):
        return False
    return True


def remove_blank_interstitial_pages(doc) -> Dict[str, int]:
    """
    Remove empty pages between content blocks in a DOCX.

    Typical artifact after frontmatter merge: a page-break lands on its own
    page after a full cover/info page, producing Cover → blank → Info → blank.

    Cleanup:
      1. Strip empty paragraphs around page-break-only paras
      2. Absorb page-break-only paragraphs into the previous content paragraph
         (avoids a break-only para starting on a new page then jumping again)
      3. Collapse consecutive page-break-only paragraphs
    """
    stats = {
        "empty_before_break": 0,
        "empty_after_break": 0,
        "empty_between_breaks": 0,
        "absorbed_breaks": 0,
        "collapsed_breaks": 0,
    }

    # Pass 1: remove empty paragraphs immediately before page-break-only paras
    changed = True
    while changed:
        changed = False
        children = list(_body_children(doc))
        for i, child in enumerate(children):
            if child.tag != qn("w:p") or not _is_page_break_only_paragraph(child):
                continue
            j = i - 1
            while j >= 0 and children[j].tag == qn("w:p"):
                prev = children[j]
                if _is_page_break_only_paragraph(prev):
                    break
                if not _paragraph_is_visually_empty(prev):
                    break
                parent = prev.getparent()
                if parent is not None:
                    parent.remove(prev)
                    stats["empty_before_break"] += 1
                    changed = True
                j -= 1
            if changed:
                break

    # Pass 2: remove empty paragraphs immediately after page-break-only paras
    changed = True
    while changed:
        changed = False
        children = list(_body_children(doc))
        for i, child in enumerate(children):
            if child.tag != qn("w:p") or not _is_page_break_only_paragraph(child):
                continue
            nxt = child.getnext()
            while nxt is not None and nxt.tag == qn("w:p"):
                if _is_page_break_only_paragraph(nxt):
                    break
                if not _paragraph_is_visually_empty(nxt):
                    break
                following = nxt.getnext()
                parent = nxt.getparent()
                if parent is not None:
                    parent.remove(nxt)
                    stats["empty_after_break"] += 1
                    changed = True
                nxt = following
            if changed:
                break

    # Pass 3: absorb page-break-only paragraphs into previous content paragraph.
    # This is the critical fix for Cover→blank→Info: a lone break paragraph that
    # starts on the next page then breaks again leaves an empty sheet.
    for child in list(_body_children(doc)):
        if child.tag != qn("w:p") or not _is_page_break_only_paragraph(child):
            continue
        prev = child.getprevious()
        while (
            prev is not None
            and prev.tag == qn("w:p")
            and _paragraph_is_visually_empty(prev)
            and not _is_page_break_only_paragraph(prev)
        ):
            pprev = prev.getprevious()
            parent = prev.getparent()
            if parent is not None:
                parent.remove(prev)
                stats["empty_before_break"] += 1
            prev = pprev

        if prev is None:
            continue
        if prev.tag == qn("w:tbl"):
            # Attach break to last paragraph inside the table's last cell
            paras = list(prev.iter(qn("w:p")))
            if not paras:
                continue
            target = paras[-1]
            if not _paragraph_has_page_break(target):
                r = OxmlElement("w:r")
                br = OxmlElement("w:br")
                br.set(qn("w:type"), "page")
                r.append(br)
                target.append(r)
            parent = child.getparent()
            if parent is not None:
                parent.remove(child)
                stats["absorbed_breaks"] += 1
            continue
        if prev.tag != qn("w:p"):
            continue
        if _is_page_break_only_paragraph(prev):
            # consecutive breaks — leave for collapse pass
            continue
        # Don't duplicate if previous already ends with a page break
        if _paragraph_has_page_break(prev):
            parent = child.getparent()
            if parent is not None:
                parent.remove(child)
                stats["absorbed_breaks"] += 1
            continue
        r = OxmlElement("w:r")
        br = OxmlElement("w:br")
        br.set(qn("w:type"), "page")
        r.append(br)
        prev.append(r)
        parent = child.getparent()
        if parent is not None:
            parent.remove(child)
            stats["absorbed_breaks"] += 1

    # Pass 4: empty-only runs between two page breaks
    children = list(_body_children(doc))
    i = 0
    while i < len(children):
        child = children[i]
        if child.tag == qn("w:p") and _paragraph_has_page_break(child):
            j = i + 1
            only_empty = True
            saw_empty = False
            while j < len(children) and children[j].tag == qn("w:p"):
                if _is_page_break_only_paragraph(children[j]) or (
                    _paragraph_has_page_break(children[j])
                    and _paragraph_is_visually_empty(children[j])
                ):
                    if saw_empty and only_empty:
                        for k in range(i + 1, j):
                            parent = children[k].getparent()
                            if parent is not None:
                                parent.remove(children[k])
                                stats["empty_between_breaks"] += 1
                        parent = children[j].getparent()
                        if parent is not None and _is_page_break_only_paragraph(children[j]):
                            parent.remove(children[j])
                            stats["collapsed_breaks"] += 1
                        children = list(_body_children(doc))
                        break
                    break
                if _paragraph_is_visually_empty(children[j]):
                    saw_empty = True
                    j += 1
                    continue
                only_empty = False
                break
        i += 1

    stats["collapsed_breaks"] += _collapse_consecutive_page_breaks(doc)
    return stats


def remove_unused_front_matter_sections(
    doc,
    active_sections: Optional[set[str]] = None,
) -> Dict[str, int]:
    """
    Remove LOF/LOT/TOC sections that were not generated for this run.
    Also strips adjacent page breaks so missing lists do not leave blank pages.
    """
    active = set(active_sections or ())
    removed = {"toc": 0, "lof": 0, "lot": 0, "headings": 0, "page_breaks": 0}

    remove_field_fns = {
        "toc": _remove_toc_field_block,
        "lof": _remove_lof_field_block,
        "lot": _remove_lot_field_block,
    }

    for key, heading_re, field_re in _FRONT_MATTER_SECTIONS:
        if key in active:
            continue
        while remove_field_fns[key](doc):
            removed[key] += 1
        removed["headings"] += _remove_meta_list_heading_paragraphs(doc, heading_re)

    removed["page_breaks"] += _collapse_consecutive_page_breaks(doc)
    return removed


def arrange_front_matter_lists(
    doc,
    *,
    include_toc: bool = True,
    include_lof: bool = True,
    include_lot: bool = True,
    page_break_before_content: bool = True,
) -> Dict[str, Any]:
    """
    Place front-matter lists just before the report body:
    Cover → Info → Table of Contents → List of Figures → List of Tables → Body.

    When no Formatify cover/info bookmark exists, lists remain at document start
    (legacy behaviour).
    """
    sections: List[Tuple[str, List[OxmlElement]]] = []
    for key, heading_re, field_re in _FRONT_MATTER_SECTIONS:
        include_flag = {
            "toc": include_toc,
            "lof": include_lof,
            "lot": include_lot,
        }[key]
        if not _front_matter_section_is_active(doc, key, heading_re, field_re, include_flag):
            continue
        block = _extract_list_section_block(doc, heading_re, field_re)
        if block and _count_entries_in_list_block(block) > 0:
            sections.append((key, block))

    if not sections:
        _collapse_consecutive_page_breaks(doc)
        return {"sections_arranged": 0, "page_breaks_inserted": 0, "section_order": []}

    for _, block in sections:
        _detach_body_elements(block)

    body = doc.element.body
    # Anchor AFTER cover/info pages when present; otherwise document start
    content_start = _lists_anchor_element(doc)

    ordered: List[OxmlElement] = []
    page_breaks = 0
    for index, (_key, block) in enumerate(sections):
        if index > 0:
            ordered.append(_build_page_break_paragraph())
            page_breaks += 1
        ordered.extend(block)

    _insert_elements_before(content_start, ordered, body=body)

    if page_break_before_content and content_start is not None:
        content_start.addprevious(_build_page_break_paragraph())
        page_breaks += 1

    _collapse_consecutive_page_breaks(doc)

    # Remove any leftover empty list headings that were not arranged
    # (e.g. blank "List of Tables" left in the wrong place).
    arranged_keys = {key for key, _ in sections}
    include_map = {"toc": include_toc, "lof": include_lof, "lot": include_lot}
    for key, heading_re, field_re in _FRONT_MATTER_SECTIONS:
        if key in arranged_keys:
            continue
        # Drop orphan headings for sections we didn't keep as populated blocks
        if not include_map[key] or not _front_matter_section_is_active(
            doc, key, heading_re, field_re, include_map[key]
        ):
            _remove_meta_list_heading_paragraphs(doc, heading_re)

    _collapse_consecutive_page_breaks(doc)

    return {
        "sections_arranged": len(sections),
        "page_breaks_inserted": page_breaks,
        "section_order": [key for key, _ in sections],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


def count_figures(doc) -> int:
    """Count images in the report body (excludes cover / project-info)."""
    body_start = find_formatify_body_start_element(doc)
    return sum(
        1
        for p in doc.paragraphs
        if paragraph_has_image(p)
        and not _paragraph_is_before_body_start(doc, p, body_start)
    )


def count_tables(doc) -> int:
    """Count tables in the report body (excludes cover / project-info)."""
    return sum(
        1 for t in doc.tables if not _element_is_before_body_start(doc, t._tbl)
    )


def analyze_document_lists(doc) -> Dict[str, Any]:
    """Build status payload for toc-check / document-lists-check endpoints."""
    headings = collect_headings(doc)
    table_count = count_tables(doc)
    figure_count = count_figures(doc)
    body_start = find_formatify_body_start_element(doc)

    tables_with_captions = 0
    for table in doc.tables:
        if _element_is_before_body_start(doc, table._tbl):
            continue
        idx = _body_index(doc, table._tbl)
        if idx > 0:
            prev = _body_children(doc)[idx - 1]
            if prev.tag == qn("w:p"):
                para = Paragraph(prev, doc.element.body)
                if paragraph_has_seq_caption(para._element, "Table") or CAPTION_TEXT_RE.match(para.text.strip()):
                    tables_with_captions += 1

    figures_with_captions = 0
    for idx, para in enumerate(doc.paragraphs):
        if _paragraph_is_before_body_start(doc, para, body_start):
            continue
        if not paragraph_has_image(para):
            continue
        if idx + 1 < len(doc.paragraphs):
            nxt = doc.paragraphs[idx + 1]
            if paragraph_has_seq_caption(nxt._element, "Figure") or CAPTION_TEXT_RE.match(nxt.text.strip()):
                figures_with_captions += 1

    return {
        "has_toc": document_has_toc(doc),
        "has_lot": document_has_lot(doc),
        "has_lof": document_has_lof(doc),
        "toc_populated": document_has_toc(doc) and not _toc_field_is_unpopulated(doc),
        "lof_populated": document_has_lof(doc) and not _lof_field_is_unpopulated(doc),
        "lot_populated": document_has_lot(doc) and not _lot_field_is_unpopulated(doc),
        "headings": headings,
        "heading_count": len(headings),
        "entry_count": len(headings),
        "table_count": table_count,
        "figure_count": figure_count,
        "tables_with_captions": tables_with_captions,
        "figures_with_captions": figures_with_captions,
        "tables_missing_captions": max(0, table_count - tables_with_captions),
        "figures_missing_captions": max(0, figure_count - figures_with_captions),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════


def refresh_list_of_figures(file_path: str) -> Dict[str, Any]:
    """
    After a figure caption changed (e.g. image replaced): renumber figure
    captions and rebuild the List of Figures entries — only if the document
    already has a List of Figures. TOC, List of Tables, headings and tables are
    not touched (unlike generate_document_lists).
    """
    from docx import Document

    doc = Document(file_path)
    has_lof = _find_section_heading_paragraph(doc, _LOF_HEADING_RE) is not None or any(
        _paragraph_has_field(p._element, LOF_FIELD_RE) for p in doc.paragraphs
    )
    # Also renumbers each body caption's visible SEQ number (1, 2, 3 …).
    entries = _prepare_lof_entries(doc)
    rebuilt = False
    if has_lof and entries:
        _remove_lof_field_block(doc)
        heading = _find_section_heading_paragraph(doc, _LOF_HEADING_RE)
        insert_lof_field(doc, heading_para=heading, entries=entries)
        normalize_bookmarks(doc)
        validate_and_repair_list_anchors(doc)
        rebuilt = True
    doc.save(file_path)
    return {"lof_rebuilt": rebuilt, "figure_count": len(entries)}


def generate_document_lists(
    file_path: str,
    formatting_rules: Optional[Dict[str, Any]] = None,
    required_sections: Optional[List[Any]] = None,
    *,
    include_toc: bool = True,
    include_lot: bool = True,
    include_lof: bool = True,
    toc_levels: str = "1-3",
    ensure_styles: bool = True,
    ensure_captions: bool = True,
    skip_table_numbering: bool = False,
) -> Dict[str, Any]:
    """
    Full pipeline: heading styles → captions → TOC / LOT / LOF fields.
    Mutates and saves the document at file_path.
    """
    from docx import Document

    doc = Document(file_path)
    # GC stale/malformed managed bookmarks before rebuilding lists
    result_norm_start = normalize_bookmarks(doc)
    result: Dict[str, Any] = {
        "headings_styled": 0,
        "table_captions_added": 0,
        "figure_captions_upgraded": 0,
        "toc_added": False,
        "lot_added": False,
        "lof_added": False,
        "entry_count": 0,
        "bookmarks_normalized_start": result_norm_start,
    }


    # Disable template outline auto-numbering on Heading styles (causes 5./6./7. leaks)
    result["heading_style_numbering_cleared"] = clear_numbering_from_heading_styles(doc)

    if ensure_styles and formatting_rules:
        heading_cleanup = sanitize_document_headings_for_lists(doc, formatting_rules)
        result["headings_demoted"] = heading_cleanup.get("demoted", 0)
        result["meta_headings_styled"] = heading_cleanup.get("meta_styled", 0)
        result["headings_styled"] = apply_heading_styles_to_document(
            doc, formatting_rules, required_sections or [],
        )
    else:
        heading_cleanup = sanitize_document_headings_for_lists(doc, formatting_rules)
        result["headings_demoted"] = heading_cleanup.get("demoted", 0)
        result["meta_headings_styled"] = heading_cleanup.get("meta_styled", 0)

    # Remove outline numbers from body prose + demote false headings before renumber
    result["outline_cleanup"] = strip_accidental_body_outline_numbering(doc)

    result["headings_renumbered"] = apply_hierarchical_heading_numbering(doc)

    # Meta titles (TOC/LOF/LOT) must never keep a leftover "5." prefix
    sanitize_document_headings_for_lists(doc, formatting_rules)

    if ensure_captions:
        from services.table_numbering_service import (
            apply_numbering_to_table_captions,
            assign_table_numbers,
        )

        if skip_table_numbering:
            # Table pipeline already numbered captions in this request;
            # numbering is idempotent but skip the duplicate pass anyway.
            applied = []
        else:
            assignments = assign_table_numbers(doc, formatting_rules)
            applied = apply_numbering_to_table_captions(
                doc, assignments, formatting_rules
            )
        result["table_captions_added"] = sum(
            1 for a in applied if a.get("caption_created")
        )
        # Keep legacy SEQ upgrade for any leftover plain captions when no rules
        if not formatting_rules:
            from docx_tools.table_processor import (
                ensure_table_captions,
                upgrade_all_table_captions_to_seq,
            )

            cap_result = ensure_table_captions(doc)
            result["table_captions_added"] += cap_result.get("captions_added", 0)
            upgrade_all_table_captions_to_seq(doc)

        fig_cap_result = ensure_figure_captions_for_lists(doc)
        result["figure_captions_upgraded"] = fig_cap_result.get("captions_added", 0)
        result["frontmatter_captions_removed"] = fig_cap_result.get(
            "frontmatter_captions_removed", 0
        )

        body_start = find_formatify_body_start_element(doc)
        for para in doc.paragraphs:
            if _paragraph_is_before_body_start(doc, para, body_start):
                continue
            if upgrade_plain_caption_to_seq(para):
                result["figure_captions_upgraded"] += 1

    ensure_update_fields_on_open(doc)

    # Keep TOC/lists after cover+info when Formatify frontmatter is present
    try:
        repair_formatify_body_start_bookmark(doc)
    except Exception as exc:
        print(f"[document_lists] body bookmark repair skipped: {exc}")

    cleanup = _cleanup_all_list_artifacts(doc)
    result["lists_cleanup"] = cleanup

    toc_entries = _prepare_toc_entries(doc, toc_levels)
    result["entry_count"] = len(toc_entries)

    if include_toc:
        if not toc_entries:
            result["toc_error"] = "No headings found to build TOC"
        else:
            _remove_toc_field_block(doc)
            toc_heading = _find_section_heading_paragraph(doc, _TOC_HEADING_RE)
            insert_toc_field(
                doc,
                levels=toc_levels,
                heading_para=toc_heading,
                entries=toc_entries,
            )
            result["toc_added"] = True
            result["toc_entry_count"] = len(toc_entries)

    # Strict order: TOC → List of Figures → List of Tables
    lof_entries = _prepare_lof_entries(doc) if include_lof else []
    if include_lof:
        _remove_lof_field_block(doc)
        if lof_entries:
            lof_heading = _find_section_heading_paragraph(doc, _LOF_HEADING_RE)
            insert_lof_field(doc, heading_para=lof_heading, entries=lof_entries)
            result["lof_added"] = True
            result["lof_entry_count"] = len(lof_entries)
        elif count_figures(doc) > 0:
            result["lof_error"] = "Figures found but captions could not be prepared"

    lot_entries = (
        _prepare_lot_entries(doc, formatting_rules) if include_lot else []
    )
    if include_lot:
        _remove_lot_field_block(doc)
        # Drop orphan empty LOT heading before rebuild
        if not lot_entries:
            _remove_meta_list_heading_paragraphs(doc, _LOT_HEADING_RE)
        if lot_entries:
            lot_heading = _find_section_heading_paragraph(doc, _LOT_HEADING_RE)
            insert_lot_field(doc, heading_para=lot_heading, entries=lot_entries)
            result["lot_added"] = True
            result["lot_entry_count"] = len(lot_entries)
        elif count_tables(doc) > 0:
            result["lot_error"] = (
                "Tables found but captions could not be prepared for List of Tables"
            )

    active_sections = {
        key for key, added in (
            ("toc", result.get("toc_added")),
            ("lot", result.get("lot_added")),
            ("lof", result.get("lof_added")),
        )
        if added
    }
    result["front_matter_pruned"] = remove_unused_front_matter_sections(doc, active_sections)

    result["front_matter_layout"] = arrange_front_matter_lists(
        doc,
        include_toc=bool(result.get("toc_added")),
        include_lot=bool(result.get("lot_added")),
        include_lof=bool(result.get("lof_added")),
    )

    # Final pass: TOC/LOF/LOT titles must never keep leftover section numbers
    sanitize_document_headings_for_lists(doc, formatting_rules)

    # GC stale/malformed managed bookmarks after lists are rebuilt, then
    # verify every PAGEREF/anchor target still resolves.
    result["bookmarks_normalized_end"] = normalize_bookmarks(doc)
    result["anchor_repair"] = validate_and_repair_list_anchors(doc)

    doc.save(file_path)
    result.update(analyze_document_lists(doc))
    return result
