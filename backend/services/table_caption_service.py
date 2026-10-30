"""
table_caption_service.py — Detect / place table captions per template rules.

When require_caption is true, missing captions are created from inferred
header text (tables historically invent short descriptions for LOT).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from docx_tools.docx_fields import (
    CAPTION_TEXT_RE,
    _body_children,
    _body_index,
    _element_is_before_body_start,
    _insert_paragraph_after,
    _insert_paragraph_before,
    paragraph_has_seq_caption,
)
from services.table_config import get_table_format_config
from docx_tools.table_processor import _infer_table_description

W_P = qn("w:p")
W_TBL = qn("w:tbl")

_CAPTION_LIKE_RE = re.compile(
    r"^(table|tbl\.?)\b[\s.:\-]*",
    re.IGNORECASE,
)
_CAPTION_NUMBER_RE = re.compile(
    r"^(?:table|tbl\.?)\s*(\d+(?:\.\d+)*)?\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
_SHORT_CAPTION_MAX_CHARS = 220
_SHORT_CAPTION_MAX_WORDS = 40


def _looks_like_caption(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > _SHORT_CAPTION_MAX_CHARS:
        return False
    if len(t.split()) > _SHORT_CAPTION_MAX_WORDS:
        return False
    return bool(_CAPTION_LIKE_RE.match(t)) or bool(CAPTION_TEXT_RE.match(t))


def extract_table_description(text: str) -> str:
    t = (text or "").strip()
    m = _CAPTION_NUMBER_RE.match(t)
    if m:
        return (m.group(2) or "").strip()
    if ":" in t:
        return t.split(":", 1)[1].strip()
    return _CAPTION_LIKE_RE.sub("", t).strip(" :.-")


def _paragraph_is_table_caption(para) -> bool:
    text = (para.text or "").strip()
    if paragraph_has_seq_caption(para._element, "Table"):
        return True
    if CAPTION_TEXT_RE.match(text) and text.lower().startswith("table"):
        return True
    return _looks_like_caption(text)


def _prev_paragraph(doc, table) -> Optional[Paragraph]:
    idx = _body_index(doc, table._tbl)
    if idx <= 0:
        return None
    prev = _body_children(doc)[idx - 1]
    if prev.tag != W_P:
        return None
    return Paragraph(prev, doc)


def _next_paragraph(doc, table) -> Optional[Paragraph]:
    nxt = table._tbl.getnext()
    while nxt is not None:
        if nxt.tag == W_P:
            return Paragraph(nxt, doc)
        if nxt.tag == W_TBL:
            return None
        nxt = nxt.getnext()
    return None


def find_caption_near_table(
    doc, table
) -> Tuple[Optional[Paragraph], Optional[str], Optional[str]]:
    """
    Returns (caption_para, position 'above'|'below', raw_text).
    Prefers the immediately adjacent caption paragraph.
    """
    above = _prev_paragraph(doc, table)
    if above is not None:
        text = (above.text or "").strip()
        if _paragraph_is_table_caption(above):
            return above, "above", text

    below = _next_paragraph(doc, table)
    if below is not None:
        text = (below.text or "").strip()
        if _paragraph_is_table_caption(below):
            return below, "below", text

    return None, None, None


def _pattern_is_valid(text: str, numbering_scheme: str, cap_para=None) -> bool:
    t = (text or "").strip()
    if numbering_scheme == "chapter":
        return bool(re.match(r"^Table\s+\d+\.\d+\s*:", t, re.IGNORECASE))
    if cap_para is not None and paragraph_has_seq_caption(cap_para._element, "Table"):
        return True
    return bool(re.match(r"^Table\s+\d+\s*:", t, re.IGNORECASE)) or bool(
        re.match(r"^Table\s*:", t, re.IGNORECASE)
    )


def _move_paragraph_before(ref_element, move_para) -> None:
    move_el = move_para._element
    if move_el.getnext() is ref_element:
        return
    parent = move_el.getparent()
    if parent is not None:
        parent.remove(move_el)
    ref_element.addprevious(move_el)


def _move_paragraph_after_table(table, move_para) -> None:
    move_el = move_para._element
    if table._tbl.getnext() is move_el:
        return
    parent = move_el.getparent()
    if parent is not None:
        parent.remove(move_el)
    table._tbl.addnext(move_el)


def set_plain_table_caption_text(para, text: str) -> None:
    p_el = para._element
    for child in list(p_el):
        if child.tag != qn("w:pPr"):
            p_el.remove(child)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    run.append(t)
    p_el.append(run)
    try:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        pass


def ensure_caption_at_position(
    doc,
    table,
    *,
    preferred_position: str = "above",
    description: Optional[str] = None,
    create_if_missing: bool = True,
) -> Tuple[Optional[Paragraph], str, bool]:
    """
    Ensure a caption paragraph sits immediately above or below the table.
    Returns (cap_para, position, created).
    """
    cap_para, position, raw = find_caption_near_table(doc, table)
    created = False
    desc = (description or "").strip()
    if not desc and raw:
        desc = extract_table_description(raw)
    if not desc:
        desc = _infer_table_description(table)

    if cap_para is None:
        if not create_if_missing:
            return None, preferred_position, False
        if preferred_position == "below":
            cap_para = _insert_paragraph_after(doc, table._tbl)
        else:
            cap_para = _insert_paragraph_before(doc, table._tbl)
        set_plain_table_caption_text(cap_para, f"Table: {desc}")
        created = True
        position = preferred_position
    elif position != preferred_position:
        if preferred_position == "above":
            _move_paragraph_before(table._tbl, cap_para)
        else:
            _move_paragraph_after_table(table, cap_para)
        position = preferred_position

    return cap_para, position or preferred_position, created


def detect_captions_for_tables(
    doc,
    formatting_rules: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Analyze captions for every body table (document order). No mutation."""
    cfg = get_table_format_config(formatting_rules)
    captioned = cfg["captioned"]
    preferred = captioned["caption_position"]
    scheme = captioned["numbering_scheme"]
    results: List[Dict[str, Any]] = []
    tbl_i = 0

    for table in doc.tables:
        if _element_is_before_body_start(doc, table._tbl):
            continue
        table_id = f"tbl{tbl_i}"
        tbl_i += 1

        cap_para, position, raw = find_caption_near_table(doc, table)
        issues: List[str] = []
        caption_found = cap_para is not None and bool(
            (raw or "").strip() or paragraph_has_seq_caption(cap_para._element, "Table")
        )
        caption_missing = not caption_found
        format_valid = False
        caption_text = raw or ""

        if caption_missing:
            issues.append("caption_missing")
        else:
            format_valid = _pattern_is_valid(caption_text, scheme, cap_para)
            if not format_valid:
                issues.append("caption_format_inconsistent")
            if position and position != preferred:
                issues.append(f"caption_position_is_{position}_expected_{preferred}")

        results.append(
            {
                "table_id": table_id,
                "caption_found": caption_found,
                "caption_missing": caption_missing,
                "caption_text": caption_text,
                "caption_description": extract_table_description(caption_text)
                if caption_text
                else "",
                "caption_position": position,
                "format_valid": format_valid,
                "issues": issues,
                "_table": table,
                "_cap_para": cap_para,
            }
        )

    return results


_LEAD_PARAS_MAX = 3


def _keep(para, with_next=None, together=None) -> None:
    pf = para.paragraph_format
    if with_next is not None:
        pf.keep_with_next = with_next
    if together is not None:
        pf.keep_together = together


def _is_heading_para(para) -> bool:
    try:
        name = (para.style.name or "").lower()
    except Exception:
        return False
    return name.startswith("heading") or name == "title"


def _flush_left(para) -> None:
    """Force zero indent (overrides style/numbering) and strip leading tabs/spaces."""
    from docx.shared import Inches
    from docx.oxml.ns import qn

    pf = para.paragraph_format
    pf.left_indent = Inches(0)
    pf.first_line_indent = Inches(0)

    # Word gives priority to the *Chars attributes; remove them
    pPr = para._element.pPr
    ind = pPr.find(qn("w:ind")) if pPr is not None else None
    if ind is not None:
        for attr in ("leftChars", "startChars", "firstLineChars",
                     "hangingChars", "start", "hanging"):
            ind.attrib.pop(qn(f"w:{attr}"), None)

    # leading tab / spaces in the first text run
    for r in para._element.findall(qn("w:r")):
        stop = False
        for child in list(r):
            if child.tag == qn("w:tab"):
                r.remove(child)
            elif child.tag == qn("w:t"):
                child.text = (child.text or "").lstrip(" \t\u00a0")
                if child.text:
                    stop = True
                    break
        if stop:
            break


def apply_table_caption_keep_chain(doc, table) -> bool:
    """Caption (+ intro paras + heading) stay on the same page as the table."""
    cap_para, position, _ = find_caption_near_table(doc, table)
    if cap_para is None:
        return False

    if position == "below":
        for cell in table.rows[-1].cells:
            for p in cell.paragraphs:
                _keep(p, with_next=True)
        _keep(cap_para, together=True)
        return True

    # caption ABOVE the table
    _keep(cap_para, with_next=True, together=True)
    el = cap_para._element.getprevious()
    pulled = 0
    while el is not None and el.tag == W_P and pulled < _LEAD_PARAS_MAX:
        if el.find(".//" + qn("w:drawing")) is not None:
            break
        p = Paragraph(el, cap_para._parent)
        if not (p.text or "").strip():
            _keep(p, with_next=True)
        elif _paragraph_is_table_caption(p):
            break
        else:
            _keep(p, with_next=True, together=True)
            if not _is_heading_para(p):
                _flush_left(p)
            pulled += 1
            if _is_heading_para(p):
                break
        el = el.getprevious()
    return True