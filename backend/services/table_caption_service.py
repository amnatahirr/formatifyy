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
from docx_tools.table_processor import _infer_table_description, dedupe_row_cells

W_P = qn("w:p")
W_TBL = qn("w:tbl")

_STATUS_SUFFIX_RE = re.compile(
    r"\s*[—–-]\s*(implemented|addressed|partially\s+addressed|not\s+addressed)"
    r"[\s.]*$",
    re.IGNORECASE,
)
_FR_NFR_RE = re.compile(r"^(FR|NFR)\d+\b", re.IGNORECASE)
_INTRO_RE = re.compile(
    r"^this\s+table\s+(?:defines?|describes?|lists?|shows?|presents?|"
    r"illustrates?|summari[sz]es?|contains?|provides?)\s+",
    re.IGNORECASE,
)
_SHAPE_PATTERNS = (
    (re.compile(r"^(?:use\s+case|uc)[\s-]*id\s*:\s*(.+)$", re.IGNORECASE),
     "Use Case Description: {0}"),
    (re.compile(r"^(?:tc|test\s+case)[\s-]*id\s*:\s*(.+)$", re.IGNORECASE),
     "Test Case: {0}"),
    (re.compile(r"^(?:fr|nfr)[\s-]*(\d+)\s*[:\-–—]?\s*(.+)$", re.IGNORECASE),
     None),  # handled below -> keep cleaned label text
)


def _deduped_header_text(table) -> str:
    """Header-row join with merged cells deduped (never repeats gridSpan text)."""
    if not table.rows:
        return ""
    cells = [
        c.text.strip()
        for c in dedupe_row_cells(table.rows[0].cells)
        if c.text.strip()
    ]
    return " — ".join(cells[:3])[:80]


def _clean_label_text(text: str) -> str:
    t = (text or "").strip().strip(" .")
    t = _STATUS_SUFFIX_RE.sub("", t).strip()
    if _FR_NFR_RE.match(t) and not re.search(r"requirements?\s*$", t, re.IGNORECASE):
        t = f"{t} Requirements"
    return t[:120]


def _nearest_label_paragraph(doc, table) -> str:
    """Nearest preceding non-empty short paragraph (<=2 back) that looks like a
    requirement/use-case label, e.g. 'FR02 - Admin Template Management'."""
    try:
        idx = _body_index(doc, table._tbl)
    except Exception:
        return ""
    children = _body_children(doc)
    scanned = 0
    for el in reversed(children[:idx]):
        if el.tag != W_P:
            continue
        para = Paragraph(el, doc)
        text = (para.text or "").strip()
        if not text:
            continue
        # Captions don't count toward the look-back window
        if _paragraph_is_table_caption(para):
            continue
        scanned += 1
        if scanned > 2:
            break
        if len(text) > 120:
            continue
        # Label/ID lines win even if they carry a heading-ish style
        # (requirement labels are often styled like sub-headings)
        if _FR_NFR_RE.match(text) or re.match(
            r"(?i)^(?:uc|tc|ucm|sc|br|sr)\s*-?\d+\b", text
        ):
            return _clean_label_text(text)
    return ""


def _intro_sentence_title(doc, table) -> str:
    """Convert an adjacent 'This table ...' sentence into a short noun phrase."""
    for cand in (_prev_paragraph(doc, table), _next_paragraph(doc, table)):
        if cand is None:
            continue
        text = (cand.text or "").strip()
        if not text or len(text) > 300:
            continue
        m = _INTRO_RE.match(text)
        if not m:
            continue
        rest = text[m.end():].strip()
        rest = re.split(r"[.;:]", rest, 1)[0].strip()
        rest = re.sub(r"^(?:the|a|an|each|all|our)\s+", "", rest, flags=re.IGNORECASE)
        rest = rest.strip(" ,")
        if 3 <= len(rest.split()) <= 10 and len(rest) <= 80:
            return rest[0].upper() + rest[1:]
    return ""


def _shape_table_title(table) -> str:
    """Key-value / label-value tables: derive title from first merged cell."""
    if not table.rows:
        return ""
    first_cells = dedupe_row_cells(table.rows[0].cells)
    if not first_cells:
        return ""
    texts = [(first_cells[0].text or "").strip()]
    # Label cell ending in ':' with the value in the next cell -> join them
    if (
        len(first_cells) > 1
        and texts[0]
        and texts[0].rstrip().endswith(":")
        and len(texts[0]) <= 40
    ):
        nxt = (first_cells[1].text or "").strip()
        if nxt:
            texts.insert(0, f"{texts[0]} {nxt}")
    for text in texts:
        if not text or len(text) > 120:
            continue
        for pattern, template in _SHAPE_PATTERNS:
            m = pattern.match(text)
            if not m:
                continue
            if template is None:
                return _clean_label_text(text)
            value = m.group(1).strip().rstrip(".")
            if value:
                return template.format(value)[:80]
    return ""


def resolve_table_title(table, doc) -> Tuple[str, str]:
    """Best-effort human title for a table caption.

    Returns (title, source) where source is one of:
    existing | label | intro | shape | none
    NEVER joins raw header cells as a title.
    """
    header_join = _deduped_header_text(table)
    # Legacy auto-titles joined raw row.cells (merged cells repeated); a stored
    # caption equal to either join is machine-generated, not a real title.
    old_join = ""
    try:
        if table.rows:
            old_join = " — ".join(
                [
                    c.text.strip()
                    for c in table.rows[0].cells
                    if c.text.strip()
                ][:3]
            )[:80]
    except Exception:
        old_join = ""

    # 1 — existing caption text next to the table
    cap_para, _pos, raw = find_caption_near_table(doc, table)
    if raw:
        desc = extract_table_description(raw)
        if desc and desc != header_join and desc != old_join:
            return desc[:120], "existing"

    # 2 — nearest preceding label paragraph (FR02 - ..., UC01, ...)
    label = _nearest_label_paragraph(doc, table)
    if label:
        return label, "label"

    # 3 — adjacent intro sentence ("This table defines ...")
    intro = _intro_sentence_title(doc, table)
    if intro:
        return intro, "intro"

    # 4 — table-shape heuristics (merged key-value first row)
    shape = _shape_table_title(table)
    if shape:
        return shape, "shape"

    # 5 — LLM fallback intentionally not wired here (sync context, no client);
    #     callers may inject one later. Last resort: no description.
    return "", "none"


def _uniquify_title(title: str, used: set) -> str:
    if not title:
        return title
    candidate = title
    i = 2
    while candidate in used:
        candidate = f"{title} ({i})"
        i += 1
    used.add(candidate)
    return candidate

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


def _split_bookmark_children(p_el):
    """Detach w:bookmarkStart/End children, preserving order. Returns (starts, ends)."""
    starts, ends = [], []
    for child in list(p_el):
        if child.tag == qn("w:bookmarkStart"):
            starts.append(child)
            p_el.remove(child)
        elif child.tag == qn("w:bookmarkEnd"):
            ends.append(child)
            p_el.remove(child)
    return starts, ends


def _reattach_bookmarks(p_el, starts, ends) -> None:
    for i, el in enumerate(starts):
        p_el.insert(i, el)
    for el in ends:
        p_el.append(el)


def _ensure_caption_style(p_el) -> None:
    """Force w:pStyle=Caption and strip heading/outline numbering props."""
    p_pr = p_el.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        p_el.insert(0, p_pr)
    for tag in ("w:numPr", "w:outlineLvl"):
        for el in list(p_pr.findall(qn(tag))):
            p_pr.remove(el)
    p_style = p_pr.find(qn("w:pStyle"))
    if p_style is None:
        p_style = OxmlElement("w:pStyle")
        p_pr.insert(0, p_style)
    p_style.set(qn("w:val"), "Caption")


def set_plain_table_caption_text(para, text: str) -> None:
    p_el = para._element
    starts, ends = _split_bookmark_children(p_el)
    for child in list(p_el):
        if child.tag != qn("w:pPr"):
            p_el.remove(child)
    _ensure_caption_style(p_el)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    run.append(t)
    p_el.append(run)
    _reattach_bookmarks(p_el, starts, ends)
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

    if cap_para is not None:
        _ensure_caption_style(cap_para._element)
        _drop_duplicate_adjacent_captions(doc, table, cap_para)

    return cap_para, position or preferred_position, created


def _drop_duplicate_adjacent_captions(doc, table, keep_para) -> None:
    """Remove extra caption-like paragraphs stacked on keep_para's side of
    the table. A caption directly touching another table is left alone —
    it may belong to that table."""
    try:
        idx = _body_index(doc, table._tbl)
    except Exception:
        return
    children = _body_children(doc)
    keep_el = keep_para._element

    def _side_of_keep():
        try:
            return -1 if _body_index(doc, keep_el) < idx else +1
        except Exception:
            return 0

    side = _side_of_keep()
    if side == 0:
        return

    def _touches_other_table(i: int) -> bool:
        # caption at children[i]; the neighbour on the far side is a table
        j = i - 1 if side == -1 else i + 1
        return 0 <= j < len(children) and children[j].tag == W_TBL

    i = idx + side
    while 0 <= i < len(children):
        el = children[i]
        if el.tag != W_P:
            break
        para = Paragraph(el, doc)
        if not _paragraph_is_table_caption(para):
            break
        if el is keep_el:
            i += side
            continue
        if _touches_other_table(i):
            break
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
        children.pop(i)


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