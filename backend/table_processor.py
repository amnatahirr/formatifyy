"""
table_processor.py — Table detection, captioning, and formatting for FORMATIFY.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from docx_fields import (
    CAPTION_TEXT_RE,
    _element_is_before_body_start,
    paragraph_has_seq_caption,
    rebuild_caption_with_seq,
    _body_children,
    _body_index,
    _paragraph_plain_text,
)

TABLE_CAPTION_RE = re.compile(r"^Table\s+(\d+)\s*:", re.IGNORECASE)

W_TBL = qn("w:tbl")
W_P = qn("w:p")


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


def _table_preview_rows(table, max_rows: int = 3) -> List[List[str]]:
    rows: List[List[str]] = []
    for row in table.rows[:max_rows]:
        rows.append([(cell.text or "").strip() for cell in row.cells])
    return rows


def _table_has_header_row(table) -> bool:
    if not table.rows:
        return False
    first = [c.text.strip() for c in table.rows[0].cells]
    if not any(first):
        return False
    if len(table.rows) < 2:
        return True
    second = [c.text.strip() for c in table.rows[1].cells]
    first_alpha = sum(1 for t in first if t and not t.replace(".", "").isdigit())
    second_alpha = sum(1 for t in second if t and not t.replace(".", "").isdigit())
    return first_alpha >= second_alpha


def _caption_paragraph_before_table(doc, table) -> Optional[Paragraph]:
    idx = _body_index(doc, table._tbl)
    if idx <= 0:
        return None
    prev = _body_children(doc)[idx - 1]
    if prev.tag != W_P:
        return None
    return Paragraph(prev, doc.element.body)


def _table_has_caption(doc, table) -> bool:
    para = _caption_paragraph_before_table(doc, table)
    if para is None:
        return False
    text = para.text.strip()
    if TABLE_CAPTION_RE.match(text):
        return True
    return paragraph_has_seq_caption(para._element, "Table")


def _infer_table_description(table) -> str:
    if not table.rows:
        return "Data table"
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    non_empty = [c for c in header_cells if c]
    if non_empty:
        joined = " — ".join(non_empty[:3])
        return joined[:80]
    for row in table.rows:
        for cell in row.cells:
            text = cell.text.strip()
            if text:
                return text[:80]
    return "Data table"


def detect_tables(doc) -> List[Dict[str, Any]]:
    """Return metadata for every table in document order."""
    tables_meta: List[Dict[str, Any]] = []
    for index, table in enumerate(doc.tables):
        row_count = len(table.rows)
        col_count = len(table.columns) if table.rows else 0
        has_header = _table_has_header_row(table)
        has_caption = _table_has_caption(doc, table)
        description = _infer_table_description(table)

        issues: List[Dict[str, str]] = []
        if not has_caption:
            issues.append({
                "code": "MISSING_CAPTION",
                "message": "Table is missing an academic-style caption (Table N: …).",
                "severity": "warning",
            })
        if row_count == 0 or col_count == 0:
            issues.append({
                "code": "EMPTY_TABLE",
                "message": "Table has no rows or columns.",
                "severity": "error",
            })
        if not has_header and row_count > 1:
            issues.append({
                "code": "NO_HEADER_ROW",
                "message": "Table may be missing a header row.",
                "severity": "info",
            })

        tables_meta.append({
            "index": index,
            "label": f"Table {index + 1}",
            "description": description,
            "row_count": row_count,
            "col_count": col_count,
            "has_header_row": has_header,
            "has_caption": has_caption,
            "issues": issues,
            "preview_rows": _table_preview_rows(table),
            "source": "docx",
        })
    return tables_meta


# ═══════════════════════════════════════════════════════════════════════════════
# CAPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def _insert_caption_before_table(doc, table, description: str) -> Paragraph:
    from docx_fields import _insert_paragraph_before

    caption_para = _insert_paragraph_before(doc, table._tbl)
    rebuild_caption_with_seq(caption_para, "Table", description)
    return caption_para


def ensure_table_captions(doc) -> Dict[str, Any]:
    """Add SEQ-based captions above tables that lack them (report body only)."""
    added = 0
    upgraded = 0

    for table in doc.tables:
        # Never caption tables on Cover / Project Details pages
        if _element_is_before_body_start(doc, table._tbl):
            continue
        cap_para = _caption_paragraph_before_table(doc, table)
        if cap_para is not None:
            text = cap_para.text.strip()
            m = CAPTION_TEXT_RE.match(text)
            if m and m.group(1).lower() == "table":
                if not paragraph_has_seq_caption(cap_para._element, "Table"):
                    rebuild_caption_with_seq(cap_para, "Table", m.group(3))
                    upgraded += 1
                continue
            if paragraph_has_seq_caption(cap_para._element, "Table"):
                continue

        description = _infer_table_description(table)
        _insert_caption_before_table(doc, table, description)
        added += 1

    return {"captions_added": added, "captions_upgraded": upgraded}


def upgrade_all_table_captions_to_seq(doc) -> int:
    upgraded = 0
    for table in doc.tables:
        cap_para = _caption_paragraph_before_table(doc, table)
        if cap_para is None:
            continue
        text = cap_para.text.strip()
        m = CAPTION_TEXT_RE.match(text)
        if m and m.group(1).lower() == "table":
            if not paragraph_has_seq_caption(cap_para._element, "Table"):
                rebuild_caption_with_seq(cap_para, "Table", m.group(3))
                upgraded += 1
    return upgraded


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

_PRESET_RULES: Dict[str, Dict[str, Any]] = {
    "academic": {
        "header_bold": True,
        "banded_rows": True,
        "borders": True,
        "center_table": True,
        "repeat_header": True,
        "auto_fit": True,
        "font_name": "Times New Roman",
        "font_size": 10,
    },
    "professional": {
        "header_bold": True,
        "banded_rows": False,
        "borders": True,
        "center_table": True,
        "repeat_header": True,
        "auto_fit": True,
        "font_name": "Calibri",
        "font_size": 10,
    },
    "minimal": {
        "header_bold": False,
        "banded_rows": False,
        "borders": True,
        "center_table": False,
        "repeat_header": False,
        "auto_fit": True,
        "font_name": "Times New Roman",
        "font_size": 10,
    },
}


def _merge_table_rules(
    preset: str = "academic",
    custom_rules: Optional[Dict[str, Any]] = None,
    template_rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rules = dict(_PRESET_RULES.get(preset, _PRESET_RULES["academic"]))
    if template_rules:
        rules.update(template_rules)
    if custom_rules:
        rules.update(custom_rules)
    return rules


def _apply_cell_font(cell, font_name: str, font_size: int, *, bold: bool = False) -> None:
    from docx.shared import Pt

    for para in cell.paragraphs:
        for run in para.runs:
            run.font.name = font_name
            run.font.size = Pt(font_size)
            run.bold = bold
        if not para.runs and para.text:
            run = para.add_run(para.text)
            para.text = ""
            run.font.name = font_name
            run.font.size = Pt(font_size)
            run.bold = bold


def _set_table_borders(table) -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        tbl.insert(0, tbl_pr)

    for tag in ("w:tblBorders",):
        existing = tbl_pr.find(qn(tag))
        if existing is not None:
            tbl_pr.remove(existing)

    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tbl_pr.append(borders)


def _apply_banded_rows(table, band_color: str = "F2F2F2") -> None:
    for r_idx, row in enumerate(table.rows):
        if r_idx == 0 or r_idx % 2 == 0:
            continue
        for cell in row.cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), band_color.replace("#", ""))
            existing = tc_pr.find(qn("w:shd"))
            if existing is not None:
                tc_pr.remove(existing)
            tc_pr.append(shd)


def format_table(table, rules: Dict[str, Any]) -> None:
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.shared import Pt

    font_name = str(rules.get("font_name", "Times New Roman"))
    font_size = int(rules.get("font_size", 10))

    try:
        table.style = "Table Grid"
    except Exception:
        pass

    if rules.get("center_table", True):
        try:
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
        except Exception:
            pass

    if rules.get("borders", True):
        _set_table_borders(table)

    if table.rows:
        for cell in table.rows[0].cells:
            _apply_cell_font(
                cell, font_name, font_size,
                bold=bool(rules.get("header_bold", True)),
            )

    for r_idx, row in enumerate(table.rows):
        if r_idx == 0:
            continue
        for cell in row.cells:
            _apply_cell_font(cell, font_name, font_size, bold=False)

    if rules.get("banded_rows", True):
        band = str(rules.get("band_color", "F2F2F2"))
        _apply_banded_rows(table, band)

    if rules.get("auto_fit", True):
        tbl = table._tbl
        tbl_pr = tbl.tblPr
        if tbl_pr is None:
            tbl_pr = OxmlElement("w:tblPr")
            tbl.insert(0, tbl_pr)
        layout = tbl_pr.find(qn("w:tblLayout"))
        if layout is None:
            layout = OxmlElement("w:tblLayout")
            tbl_pr.append(layout)
        layout.set(qn("w:type"), "autofit")


def format_tables_in_document(
    doc,
    selected_indices: Optional[Set[int]] = None,
    *,
    preset: str = "academic",
    custom_rules: Optional[Dict[str, Any]] = None,
    template_rules: Optional[Dict[str, Any]] = None,
    add_captions: bool = True,
) -> Dict[str, Any]:
    """Apply table formatting and optional captions to selected tables."""
    rules = _merge_table_rules(preset, custom_rules, template_rules)
    formatted: List[int] = []

    if add_captions:
        ensure_table_captions(doc)

    for index, table in enumerate(doc.tables):
        if selected_indices is not None and index not in selected_indices:
            continue
        format_table(table, rules)
        formatted.append(index)

    return {
        "formatted_tables": formatted,
        "formatted_count": len(formatted),
        "rules_applied": rules,
    }
