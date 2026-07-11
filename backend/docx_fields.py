"""
docx_fields.py — Microsoft Word field insertion for TOC, LOT, and LOF.

python-docx does not expose TOC/list fields natively. This module builds the
required OOXML (w:fldChar / w:instrText) so lists update via Word's
"Update Table" / "Update Field" actions.
"""

from __future__ import annotations

import re
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

_HEADING_STYLE_RE = re.compile(r"heading\s*(\d+)", re.IGNORECASE)
_NUMBERING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
_BODY_SENTENCE_RE = re.compile(r"[.!?]\s+\S")
_MAX_TOC_HEADING_WORDS = 10
_MAX_TOC_HEADING_CHARS = 90

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


def _append_seq_field_runs(paragraph_el: OxmlElement, seq_name: str) -> None:
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
    t.text = "1"
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

    _demote_paragraph_from_heading(para)
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
        if is_meta:
            _style_meta_list_heading(para, doc, formatting_rules)
            stats["meta_styled"] += 1
            continue

        level = _heading_level_from_paragraph(para)
        if level is None:
            continue

        if not _is_valid_toc_source_heading(text):
            _demote_paragraph_from_heading(para)
            stats["demoted"] += 1

    return stats


def ensure_figure_captions_for_lists(doc) -> Dict[str, Any]:
    """Ensure every detected figure has a SEQ-based caption for LOF."""
    added = 0
    image_indices = [
        i for i, p in enumerate(doc.paragraphs) if paragraph_has_image(p)
    ]

    for fig_num, img_idx in enumerate(image_indices, start=1):
        para = doc.paragraphs[img_idx]
        cap_para = None
        if img_idx + 1 < len(doc.paragraphs):
            nxt = doc.paragraphs[img_idx + 1]
            nxt_text = nxt.text.strip()
            if (
                not paragraph_has_image(nxt)
                and (
                    CAPTION_TEXT_RE.match(nxt_text)
                    or paragraph_has_seq_caption(nxt._element, "Figure")
                )
            ):
                cap_para = nxt

        if cap_para is None:
            cap_para = _insert_paragraph_after(doc, para._element)
            rebuild_caption_with_seq(
                cap_para,
                "Figure",
                "Illustration related to the document content.",
            )
            added += 1
        elif not paragraph_has_seq_caption(cap_para._element, "Figure"):
            m = CAPTION_TEXT_RE.match(cap_para.text.strip())
            description = m.group(3) if m else cap_para.text.strip()
            rebuild_caption_with_seq(cap_para, "Figure", description)
            added += 1

    return {"captions_ensured": len(image_indices), "captions_added": added}


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
    for idx, para in enumerate(doc.paragraphs):
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
    return _is_valid_toc_source_heading(text)


def apply_hierarchical_heading_numbering(doc) -> int:
    """
    Renumber valid content headings from 1 using 1, 1.1, 2, 2.1 …
    Front-matter list headings and invalid heading-styled body text are skipped.
    """
    from reformatter import (
        _HeadingNumberTracker,
        _format_numbered_heading,
        _set_paragraph_text_preserve_style,
    )

    tracker = _HeadingNumberTracker()
    updated = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if not _should_number_heading_paragraph(para, text):
            continue
        level = _heading_level_from_paragraph(para)
        if level is None:
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
    Ensure detected template headings use built-in Word Heading N styles.
    Returns count of paragraphs updated.
    """
    from reformatter import _apply_word_heading, _detect_heading_level, _parse_section_map, parse_template_styles
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

    updated = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        level = _detect_heading_level(para, text, section_map)
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


def rebuild_caption_with_seq(para, label: str, description: str) -> None:
    """
    Rebuild a caption paragraph using a Word SEQ field.
    label: 'Table' or 'Figure'
    description: text after the number (e.g. 'User Dataset Description')
    """
    label = label.strip().title()
    p_el = para._element

    for child in list(p_el):
        if child.tag != qn("w:pPr"):
            p_el.remove(child)

    _set_caption_paragraph_properties(p_el, center=True)
    p_el.append(_text_run(f"{label} "))
    _append_seq_field_runs(p_el, label)
    suffix = description.strip()
    p_el.append(_text_run(f": {suffix}" if suffix else ":"))


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


def document_has_lot(doc) -> bool:
    for para in doc.paragraphs:
        if _paragraph_has_field(para._element, LOT_FIELD_RE):
            return True
    return False


def document_has_lof(doc) -> bool:
    for para in doc.paragraphs:
        if _paragraph_has_field(para._element, LOF_FIELD_RE):
            return True
    return False


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


def _calculate_toc_tab_position(doc) -> int:
    """Return right-aligned tab position in twips for TOC dot leaders."""
    try:
        section = doc.sections[0]
        content_width = section.page_width - section.left_margin - section.right_margin
        twips = int(content_width / 635)
        return max(4000, twips - 120)
    except Exception:
        return 9000


def _append_pageref_field_runs(paragraph_el: OxmlElement, bookmark_name: str) -> None:
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
    t.text = "1"
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
) -> OxmlElement:
    p = OxmlElement("w:p")
    p_pr = OxmlElement("w:pPr")

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
    t = OxmlElement("w:t")
    t.text = text
    r_link.append(t)
    hyperlink.append(r_link)
    p.append(hyperlink)

    r_tab = OxmlElement("w:r")
    r_tab.append(OxmlElement("w:tab"))
    p.append(r_tab)

    _append_pageref_field_runs(p, bookmark_name)
    return p


def _build_toc_field_start_paragraph(instruction: str) -> OxmlElement:
    p = OxmlElement("w:p")

    r_begin = OxmlElement("w:r")
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    fld_begin.set(qn("w:dirty"), "true")
    r_begin.append(fld_begin)
    p.append(r_begin)

    r_instr = OxmlElement("w:r")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = f" {instruction.strip()} "
    r_instr.append(instr_text)
    p.append(r_instr)

    r_sep = OxmlElement("w:r")
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r_sep.append(fld_sep)
    p.append(r_sep)
    return p


def _build_toc_field_end_paragraph() -> OxmlElement:
    p = OxmlElement("w:p")
    r_end = OxmlElement("w:r")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r_end.append(fld_end)
    p.append(r_end)
    return p


def _prepare_toc_entries(doc, levels: str = "1-3") -> List[Dict[str, Any]]:
    """Collect TOC source headings, add bookmarks, and exclude meta list headings."""
    min_level, max_level = _parse_toc_level_range(levels)
    next_bookmark_id = _get_max_bookmark_id(doc) + 1
    entries: List[Dict[str, Any]] = []

    for idx, para in enumerate(doc.paragraphs):
        if _paragraph_in_generated_list(para):
            continue
        level = _heading_level_from_paragraph(para)
        if level is None or level < min_level or level > max_level:
            continue

        raw_text = para.text.strip()
        if not raw_text or not _is_valid_toc_source_heading(raw_text):
            continue

        display_text = _extract_toc_display_text(raw_text)
        bookmark_name = f"_Toc{next_bookmark_id:09d}"
        _ensure_bookmark_on_paragraph(para, bookmark_name, next_bookmark_id)
        entries.append({
            "paragraph_index": idx,
            "level": level,
            "text": display_text,
            "raw_text": raw_text,
            "bookmark": bookmark_name,
        })
        next_bookmark_id += 1

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
    """Remove an existing list field block (single- or multi-paragraph)."""
    body = doc.element.body
    removed_any = False

    while True:
        children = list(body)
        start_idx = None
        for i, child in enumerate(children):
            if child.tag == qn("w:p") and _paragraph_has_field(child, field_pattern):
                start_idx = i
                break
        if start_idx is None:
            break

        for j in range(start_idx, len(children)):
            el = children[j]
            if el.tag != qn("w:p"):
                continue
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
                removed_any = True
            if _paragraph_is_outer_list_field_end(el, field_pattern):
                break

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


def _remove_toc_field_block(doc) -> bool:
    return _remove_list_field_block(doc, TOC_FIELD_RE)


def _remove_lof_field_block(doc) -> bool:
    return _remove_list_field_block(doc, LOF_FIELD_RE)


def _remove_lot_field_block(doc) -> bool:
    return _remove_list_field_block(doc, LOT_FIELD_RE)


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
    return _list_field_is_unpopulated(
        doc,
        LOF_FIELD_RE,
        ("right-click", "update field", "no table of figures entries"),
    )


def _lot_field_is_unpopulated(doc) -> bool:
    return _list_field_is_unpopulated(
        doc,
        LOT_FIELD_RE,
        ("right-click", "update field", "no table of tables entries"),
    )


def _prepare_lof_entries(doc) -> List[Dict[str, Any]]:
    """Collect figure captions and ensure SEQ fields/bookmarks exist."""
    next_bookmark_id = _get_max_bookmark_id(doc) + 1
    entries: List[Dict[str, Any]] = []

    ensure_figure_captions_for_lists(doc)

    for idx, para in enumerate(doc.paragraphs):
        if not paragraph_has_image(para):
            continue

        cap_para = None
        cap_text = ""
        if idx + 1 < len(doc.paragraphs):
            nxt = doc.paragraphs[idx + 1]
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

        if not paragraph_has_seq_caption(cap_para._element, "Figure"):
            m = CAPTION_TEXT_RE.match(cap_text)
            description = m.group(3) if m else cap_text
            rebuild_caption_with_seq(cap_para, "Figure", description)

        bookmark_name = f"_Toc{next_bookmark_id:09d}"
        _ensure_bookmark_on_paragraph(cap_para, bookmark_name, next_bookmark_id)
        entries.append({
            "paragraph_index": idx,
            "level": 1,
            "text": cap_para.text.strip() or cap_text,
            "bookmark": bookmark_name,
        })
        next_bookmark_id += 1

    return entries


def _prepare_lot_entries(doc) -> List[Dict[str, Any]]:
    """Collect table captions for LOT generation."""
    from table_processor import ensure_table_captions

    ensure_table_captions(doc)
    next_bookmark_id = _get_max_bookmark_id(doc) + 1
    entries: List[Dict[str, Any]] = []

    for table in doc.tables:
        idx = _body_index(doc, table._tbl)
        if idx <= 0:
            continue
        prev = _body_children(doc)[idx - 1]
        if prev.tag != qn("w:p"):
            continue
        cap_para = Paragraph(prev, doc.element.body)
        cap_text = cap_para.text.strip()
        if not cap_text and not paragraph_has_seq_caption(cap_para._element, "Table"):
            continue

        if not paragraph_has_seq_caption(cap_para._element, "Table"):
            m = CAPTION_TEXT_RE.match(cap_text)
            description = m.group(3) if m else cap_text
            rebuild_caption_with_seq(cap_para, "Table", description)

        bookmark_name = f"_Toc{next_bookmark_id:09d}"
        _ensure_bookmark_on_paragraph(cap_para, bookmark_name, next_bookmark_id)
        entries.append({
            "paragraph_index": idx - 1,
            "level": 1,
            "text": cap_para.text.strip() or cap_text,
            "bookmark": bookmark_name,
        })
        next_bookmark_id += 1

    return entries


def _insert_populated_list_block(
    doc,
    after_element: OxmlElement,
    instruction: str,
    entries: List[Dict[str, Any]],
) -> None:
    tab_pos = _calculate_toc_tab_position(doc)
    elements: List[OxmlElement] = [_build_toc_field_start_paragraph(instruction)]
    for entry in entries:
        elements.append(
            _build_toc_entry_paragraph(
                entry["level"],
                entry["text"],
                entry["bookmark"],
                tab_pos,
            )
        )
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
    from docx_styles import force_heading_style

    if heading_para is None:
        body = doc.element.body
        first = body[0] if len(body) else None
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
        body = doc.element.body
        first = body[0] if len(body) else None
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
        body = doc.element.body
        first = body[0] if len(body) else None
        if first is not None:
            heading_para = _insert_paragraph_before(doc, first)
        else:
            heading_para = doc.add_paragraph()
        heading_para.add_run("List of Tables")
        _style_meta_list_heading(heading_para, doc)

    _insert_populated_list_block(doc, heading_para._element, instruction, lot_entries)
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
        body = doc.element.body
        first = body[0] if len(body) else None
        if first is not None:
            heading_para = _insert_paragraph_before(doc, first)
        else:
            heading_para = doc.add_paragraph()
        heading_para.add_run("List of Figures")
        _style_meta_list_heading(heading_para, doc)

    _insert_populated_list_block(doc, heading_para._element, instruction, lof_entries)
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
    """Return heading + populated field block elements for one front-matter list."""
    heading_para = _find_section_heading_paragraph(doc, heading_re)
    if heading_para is None:
        return None

    elements: List[OxmlElement] = [heading_para._element]
    sibling = heading_para._element.getnext()
    saw_field = False

    while sibling is not None and sibling.tag == qn("w:p"):
        text = _paragraph_plain_text(sibling)
        if text and _is_other_meta_list_heading(text, heading_re):
            break

        elements.append(sibling)
        if _paragraph_has_field(sibling, field_re):
            saw_field = True
        if saw_field and _paragraph_is_outer_list_field_end(sibling, field_re):
            return elements
        sibling = sibling.getnext()

    return elements if saw_field else None


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
    Place front-matter lists at the document start:
    - Table of Contents on the first page
    - List of Figures on the next page (only when figures exist)
    - List of Tables on the following page (only when tables exist)
    Main body content begins after a final page break.
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
    content_start = body[0] if len(body) else None

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

    return {
        "sections_arranged": len(sections),
        "page_breaks_inserted": page_breaks,
        "section_order": [key for key, _ in sections],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


def count_figures(doc) -> int:
    return sum(1 for p in doc.paragraphs if paragraph_has_image(p))


def count_tables(doc) -> int:
    return len(doc.tables)


def analyze_document_lists(doc) -> Dict[str, Any]:
    """Build status payload for toc-check / document-lists-check endpoints."""
    headings = collect_headings(doc)
    table_count = count_tables(doc)
    figure_count = count_figures(doc)

    tables_with_captions = 0
    for table in doc.tables:
        idx = _body_index(doc, table._tbl)
        if idx > 0:
            prev = _body_children(doc)[idx - 1]
            if prev.tag == qn("w:p"):
                para = Paragraph(prev, doc.element.body)
                if paragraph_has_seq_caption(para._element, "Table") or CAPTION_TEXT_RE.match(para.text.strip()):
                    tables_with_captions += 1

    figures_with_captions = 0
    for idx, para in enumerate(doc.paragraphs):
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
) -> Dict[str, Any]:
    """
    Full pipeline: heading styles → captions → TOC / LOT / LOF fields.
    Mutates and saves the document at file_path.
    """
    from docx import Document

    from table_processor import ensure_table_captions, upgrade_all_table_captions_to_seq

    doc = Document(file_path)
    result: Dict[str, Any] = {
        "headings_styled": 0,
        "table_captions_added": 0,
        "figure_captions_upgraded": 0,
        "toc_added": False,
        "lot_added": False,
        "lof_added": False,
        "entry_count": 0,
    }

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

    result["headings_renumbered"] = apply_hierarchical_heading_numbering(doc)

    if ensure_captions:
        cap_result = ensure_table_captions(doc)
        result["table_captions_added"] = cap_result.get("captions_added", 0)
        upgrade_all_table_captions_to_seq(doc)

        fig_cap_result = ensure_figure_captions_for_lists(doc)
        result["figure_captions_upgraded"] = fig_cap_result.get("captions_added", 0)

        for para in doc.paragraphs:
            if upgrade_plain_caption_to_seq(para):
                result["figure_captions_upgraded"] += 1

    ensure_update_fields_on_open(doc)

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

    lot_entries = _prepare_lot_entries(doc) if include_lot else []
    if include_lot and lot_entries:
        _remove_lot_field_block(doc)
        lot_heading = _find_section_heading_paragraph(doc, _LOT_HEADING_RE)
        insert_lot_field(doc, heading_para=lot_heading, entries=lot_entries)
        result["lot_added"] = True
        result["lot_entry_count"] = len(lot_entries)

    lof_entries = _prepare_lof_entries(doc) if include_lof else []
    if include_lof and lof_entries:
        _remove_lof_field_block(doc)
        lof_heading = _find_section_heading_paragraph(doc, _LOF_HEADING_RE)
        insert_lof_field(doc, heading_para=lof_heading, entries=lof_entries)
        result["lof_added"] = True
        result["lof_entry_count"] = len(lof_entries)
    elif include_lof and count_figures(doc) > 0 and not lof_entries:
        result["lof_error"] = "Figures found but captions could not be prepared"

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

    doc.save(file_path)
    result.update(analyze_document_lists(doc))
    return result
