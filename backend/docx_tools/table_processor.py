"""
table_processor.py — Table detection, captioning, and formatting for FORMATIFY.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from docx_tools.docx_fields import (
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


def _table_preview_rows(table, max_rows: int = 8) -> List[List[str]]:
    rows: List[List[str]] = []
    row_count = min(max_rows, len(table.rows))
    col_count = len(table.columns) if table.rows else 0
    for r_idx in range(row_count):
        row_vals: List[str] = []
        for c_idx in range(col_count):
            row_vals.append((table.cell(r_idx, c_idx).text or "").strip())
        rows.append(row_vals)
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


def _header_cell_is_bold(cell) -> bool:
    """True when any non-empty run in the cell is explicitly bold."""
    saw_text = False
    for para in cell.paragraphs:
        for run in para.runs:
            if not (run.text or "").strip():
                continue
            saw_text = True
            if run.font.bold is True:
                return True
            r_pr = run._element.find(qn("w:rPr"))
            if r_pr is not None and r_pr.find(qn("w:b")) is not None:
                return True
    return False if saw_text else False


def _header_cell_has_shading(cell) -> bool:
    tc_pr = cell._tc.find(qn("w:tcPr"))
    if tc_pr is None:
        return False
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        return False
    fill = (shd.get(qn("w:fill")) or "").strip().upper()
    return fill not in ("", "AUTO", "FFFFFF", "NONE")


def _detect_header_style_issues(
    table,
    *,
    require_bold: bool,
    require_shading: bool,
) -> List[Dict[str, Any]]:
    """Flag missing header bold / shading when the template requires them."""
    if not table.rows:
        return []
    if not _table_has_header_row(table):
        return []

    issues: List[Dict[str, Any]] = []
    header = table.rows[0]
    col_count = len(table.columns)
    bold_missing = 0
    shade_missing = 0
    for c_idx in range(col_count):
        cell = table.cell(0, c_idx)
        if not (cell.text or "").strip():
            continue
        if require_bold and not _header_cell_is_bold(cell):
            bold_missing += 1
        if require_shading and not _header_cell_has_shading(cell):
            shade_missing += 1

    if require_bold and bold_missing > 0:
        issues.append({
            "code": "HEADER_STYLE",
            "message": (
                "Header row is not bold. Apply template header style "
                "(bold header text)."
            ),
            "severity": "warning",
            "action": "apply_table_style",
        })
    if require_shading and shade_missing > 0:
        issues.append({
            "code": "HEADER_SHADING",
            "message": (
                "Header row is missing the template background shading."
            ),
            "severity": "info",
            "action": "apply_table_style",
        })
    return issues


def _caption_paragraph_before_table(doc, table) -> Optional[Paragraph]:
    idx = _body_index(doc, table._tbl)
    if idx <= 0:
        return None
    prev = _body_children(doc)[idx - 1]
    if prev.tag != W_P:
        return None
    return Paragraph(prev, doc.element.body)


def _table_has_caption(doc, table) -> bool:
    from services.table_caption_service import find_caption_near_table

    cap_para, _pos, raw = find_caption_near_table(doc, table)
    if cap_para is None:
        return False
    if (raw or "").strip():
        return True
    return paragraph_has_seq_caption(cap_para._element, "Table")


def dedupe_row_cells(cells) -> List:
    """Drop repeated cells produced by merged (gridSpan/vMerge) regions.

    python-docx ``row.cells`` repeats the same ``w:tc`` for merged columns;
    identity on ``cell._tc`` is the reliable dedupe key.
    """
    seen = set()
    out = []
    for cell in cells:
        key = id(cell._tc)
        if key in seen:
            continue
        seen.add(key)
        out.append(cell)
    return out


def _infer_table_description(table) -> str:
    if not table.rows:
        return "Data table"
    header_cells = [c.text.strip() for c in dedupe_row_cells(table.rows[0].cells)]
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


def detect_tables(
    doc,
    formatting_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return metadata for every body table in document order."""
    from services.table_caption_service import detect_captions_for_tables
    from services.table_config import get_table_format_config
    from services.table_reference_validator import validate_table_references
    from services.table_numbering_service import assign_table_numbers

    cfg = get_table_format_config(formatting_rules)
    captioned = cfg["captioned"]
    caption_rows = detect_captions_for_tables(doc, formatting_rules)
    by_tbl_el = {
        id(row["_table"]._tbl): row for row in caption_rows if row.get("_table") is not None
    }

    # Soft reference check (non-mutating) for orphaned tables
    assignments = assign_table_numbers(doc, formatting_rules)
    # Attach temporary labels for validator without mutating captions
    soft_assignments = []
    for a in assignments:
        soft_assignments.append(
            {
                **{k: v for k, v in a.items() if not k.startswith("_")},
                "label": a.get("label_prefix") or f"Table {a['n']}",
                "table_id": a["table_id"],
            }
        )
    ref_report = validate_table_references(
        doc,
        soft_assignments,
        require_intext_reference=bool(captioned.get("require_intext_reference")),
    )
    orphaned_ids = {
        o.get("table_id") for o in ref_report.get("orphaned_tables", [])
    }

    tables_meta: List[Dict[str, Any]] = []
    body_i = 0
    for index, table in enumerate(doc.tables):
        if _element_is_before_body_start(doc, table._tbl):
            continue
        table_id = f"tbl{body_i}"
        body_i += 1

        row_count = len(table.rows)
        col_count = len(table.columns) if table.rows else 0
        has_header = _table_has_header_row(table)
        cap_info = by_tbl_el.get(id(table._tbl), {})
        has_caption = bool(cap_info.get("caption_found"))
        description = _infer_table_description(table)
        if cap_info.get("caption_description"):
            description = cap_info["caption_description"]

        issues: List[Dict[str, str]] = []
        if not has_caption and captioned.get("require_caption", True):
            issues.append({
                "code": "MISSING_CAPTION",
                "message": "Table is missing an academic-style caption (Table N: …).",
                "severity": "warning",
            })
        for flag in cap_info.get("issues") or []:
            if flag == "caption_missing":
                continue  # already covered
            if flag == "caption_format_inconsistent":
                issues.append({
                    "code": "CAPTION_FORMAT",
                    "message": (
                        "Caption format does not match the template pattern "
                        f"({cfg.get('table_caption_format_pattern')})."
                    ),
                    "severity": "warning",
                })
            elif flag.startswith("caption_position_is_"):
                preferred = captioned.get("caption_position", "above")
                issues.append({
                    "code": "CAPTION_POSITION",
                    "message": (
                        f"Caption should be placed {preferred} the table "
                        "per template rules."
                    ),
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

        style = cfg.get("table_style") or {}
        # Academic tables: header text should be bold. Shading only when template asks.
        issues.extend(
            _detect_header_style_issues(
                table,
                require_bold=True,
                require_shading=bool(style.get("header_row_shading")),
            )
        )

        if (
            captioned.get("require_intext_reference")
            and table_id in orphaned_ids
        ):
            issues.append({
                "code": "MISSING_INTEXT_REFERENCE",
                "message": "No in-text reference to this table was found.",
                "severity": "warning",
            })

        empty_cells = _find_empty_cells(table)
        for cell_pos in empty_cells:
            r = int(cell_pos["row"])
            c = int(cell_pos["col"])
            issues.append({
                "code": "EMPTY_CELL",
                "message": (
                    f"Empty cell at row {r + 1}, column {c + 1}. "
                    "Add text to fill this cell."
                ),
                "severity": "warning",
                "row": r,
                "col": c,
                "action": "fill_cell",
            })

        expected_font = str(style.get("font_name") or "Times New Roman").strip()
        expected_size = int(style.get("font_size") or 12)
        for bad in _find_inconsistent_font_cells(
            table,
            expected_font_name=expected_font,
            expected_font_size=expected_size,
        ):
            r = int(bad["row"])
            c = int(bad["col"])
            reason = "; ".join(bad.get("reasons") or [])
            issues.append({
                "code": "FONT_INCONSISTENT",
                "message": (
                    f"Inconsistent font at row {r + 1}, column {c + 1} "
                    f"({reason}). Should match {expected_font} {expected_size}pt."
                ),
                "severity": "warning",
                "row": r,
                "col": c,
                "action": "normalize_font",
                "font_name": bad.get("font_name"),
                "font_size": bad.get("font_size"),
                "expected_font_name": expected_font,
                "expected_font_size": expected_size,
            })

        tables_meta.append({
            "index": index,
            "table_id": table_id,
            "label": f"Table {body_i}",
            "description": description,
            "row_count": row_count,
            "col_count": col_count,
            "has_header_row": has_header,
            "has_caption": has_caption,
            "caption_position": cap_info.get("caption_position"),
            "caption_text": cap_info.get("caption_text") or "",
            "issues": issues,
            "preview_rows": _table_preview_rows(table),
            "source": "docx",
        })
    return tables_meta


# ═══════════════════════════════════════════════════════════════════════════════
# CAPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def _insert_caption_before_table(doc, table, description: str) -> Paragraph:
    from docx_tools.docx_fields import _insert_paragraph_before

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
    from docx.shared import Pt, RGBColor

    def _style_run(run) -> None:
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.bold = bold
        run.italic = False
        run.font.color.rgb = RGBColor(0, 0, 0)
        # Force ASCII/hAnsi so Word does not keep a theme / east-Asian fallback font
        r_pr = run._element.get_or_add_rPr()
        r_fonts = r_pr.find(qn("w:rFonts"))
        if r_fonts is None:
            r_fonts = OxmlElement("w:rFonts")
            r_pr.insert(0, r_fonts)
        r_fonts.set(qn("w:ascii"), font_name)
        r_fonts.set(qn("w:hAnsi"), font_name)
        r_fonts.set(qn("w:cs"), font_name)
        r_fonts.set(qn("w:eastAsia"), font_name)

    for para in cell.paragraphs:
        runs = list(para.runs)
        if not runs:
            text = (para.text or "").strip()
            if not text:
                continue
            # Clear leftover children except pPr, then add one styled run
            for child in list(para._element):
                if child.tag != qn("w:pPr"):
                    para._element.remove(child)
            run = para.add_run(text)
            _style_run(run)
            continue
        for run in runs:
            _style_run(run)


def _set_tbl_look(table, *, header_shading: bool, banded: bool) -> None:
    """Disable Word style-driven first-row / banded coloring unless requested."""
    tbl_pr = _ensure_tbl_pr(table)
    existing = tbl_pr.find(qn("w:tblLook"))
    if existing is not None:
        tbl_pr.remove(existing)
    look = OxmlElement("w:tblLook")
    look.set(qn("w:firstRow"), "1" if header_shading else "0")
    look.set(qn("w:lastRow"), "0")
    look.set(qn("w:firstColumn"), "0")
    look.set(qn("w:lastColumn"), "0")
    look.set(qn("w:noHBand"), "0" if banded else "1")
    look.set(qn("w:noVBand"), "1")
    # Bitmask: noHBand (0x0200) | noVBand (0x0400) when banding off
    look.set(qn("w:val"), "0600" if not banded else "0020")
    tbl_pr.append(look)


def _clear_all_table_shading(table) -> None:
    row_count = len(table.rows)
    col_count = len(table.columns) if table.rows else 0
    for r_idx in range(row_count):
        for c_idx in range(col_count):
            _clear_cell_shading(table.cell(r_idx, c_idx))


def _run_font_snapshot(run) -> Dict[str, Any]:
    from docx.shared import Pt

    name = None
    try:
        name = run.font.name
    except Exception:
        name = None
    if not name:
        r_pr = run._element.find(qn("w:rPr"))
        if r_pr is not None:
            r_fonts = r_pr.find(qn("w:rFonts"))
            if r_fonts is not None:
                name = (
                    r_fonts.get(qn("w:ascii"))
                    or r_fonts.get(qn("w:hAnsi"))
                    or r_fonts.get(qn("w:cs"))
                )
    size_pt = None
    try:
        if run.font.size is not None:
            size_pt = round(run.font.size.pt, 1)
    except Exception:
        size_pt = None
    bold = bool(run.bold) if run.bold is not None else False
    return {
        "font_name": (name or "").strip() or None,
        "font_size": size_pt,
        "bold": bold,
    }


def _cell_font_snapshot(cell) -> Optional[Dict[str, Any]]:
    """Dominant font of non-empty text in a cell."""
    samples: List[Dict[str, Any]] = []
    for para in cell.paragraphs:
        for run in para.runs:
            if not (run.text or "").strip():
                continue
            samples.append(_run_font_snapshot(run))
    if not samples:
        return None
    # Prefer first non-empty run (visible start of cell)
    return samples[0]


def _find_inconsistent_font_cells(
    table,
    *,
    expected_font_name: Optional[str] = None,
    expected_font_size: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Find body/header cells whose font name or size differs from the table's
    dominant font (or from expected template values when provided).
    """
    row_count = len(table.rows)
    col_count = len(table.columns) if table.rows else 0
    cells_meta: List[Dict[str, Any]] = []

    for r_idx in range(row_count):
        for c_idx in range(col_count):
            cell = table.cell(r_idx, c_idx)
            snap = _cell_font_snapshot(cell)
            if snap is None:
                continue
            cells_meta.append({"row": r_idx, "col": c_idx, **snap})

    if not cells_meta:
        return []

    # Dominant font name / size among cells that declare them
    name_counts: Dict[str, int] = {}
    size_counts: Dict[float, int] = {}
    for m in cells_meta:
        if m.get("font_name"):
            name_counts[m["font_name"]] = name_counts.get(m["font_name"], 0) + 1
        if m.get("font_size") is not None:
            size_counts[m["font_size"]] = size_counts.get(m["font_size"], 0) + 1

    dominant_name = expected_font_name or (
        max(name_counts, key=name_counts.get) if name_counts else None
    )
    dominant_size = (
        float(expected_font_size)
        if expected_font_size is not None
        else (max(size_counts, key=size_counts.get) if size_counts else None)
    )

    inconsistent: List[Dict[str, Any]] = []
    for m in cells_meta:
        reasons: List[str] = []
        cell_name = m.get("font_name")
        cell_size = m.get("font_size")
        if dominant_name and cell_name and cell_name.lower() != dominant_name.lower():
            reasons.append(f"font '{cell_name}' != '{dominant_name}'")
        if (
            dominant_size is not None
            and cell_size is not None
            and abs(float(cell_size) - float(dominant_size)) >= 0.5
        ):
            reasons.append(f"size {cell_size}pt != {dominant_size}pt")
        # Also flag when expected template font is set and cell has no name
        # but others do — skip empty name if majority also has no name
        if not reasons:
            continue
        inconsistent.append(
            {
                "row": m["row"],
                "col": m["col"],
                "font_name": cell_name,
                "font_size": cell_size,
                "expected_font_name": dominant_name,
                "expected_font_size": dominant_size,
                "reasons": reasons,
            }
        )
    return inconsistent


def normalize_table_fonts(
    table,
    *,
    font_name: str = "Times New Roman",
    font_size: int = 12,
    header_bold: bool = False,
) -> Dict[str, Any]:
    """Force every cell to the same font name/size; bold only header if requested."""
    row_count = len(table.rows)
    col_count = len(table.columns) if table.rows else 0
    fixed = 0
    for r_idx in range(row_count):
        for c_idx in range(col_count):
            cell = table.cell(r_idx, c_idx)
            _apply_cell_font(
                cell,
                font_name,
                font_size,
                bold=bool(header_bold) if r_idx == 0 else False,
            )
            fixed += 1
    return {
        "cells_normalized": fixed,
        "font_name": font_name,
        "font_size": font_size,
        "header_bold": bool(header_bold),
    }


def _ensure_tbl_pr(table):
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        tbl.insert(0, tbl_pr)
    return tbl_pr


def _set_table_borders(
    table,
    *,
    border_style: str = "single_line",
    color: str = "000000",
    size: int = 4,
) -> None:
    tbl_pr = _ensure_tbl_pr(table)
    existing = tbl_pr.find(qn("w:tblBorders"))
    if existing is not None:
        tbl_pr.remove(existing)

    if border_style == "none" or size <= 0:
        return

    val = "single"
    if border_style == "double_line":
        val = "double"
    elif border_style == "academic_standard":
        val = "single"

    color = (color or "000000").replace("#", "").upper()
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), val)
        el.set(qn("w:sz"), str(max(0, int(size))))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tbl_pr.append(borders)


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    existing = tc_pr.find(qn("w:shd"))
    if existing is not None:
        tc_pr.remove(existing)
    raw = (fill or "").replace("#", "").strip().upper()
    if not raw or raw in ("AUTO", "NONE", "FFFFFF"):
        # Explicit white / none — use auto so Word shows a plain white cell
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "auto")
        tc_pr.append(shd)
        return
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), raw)
    tc_pr.append(shd)


def _clear_cell_shading(cell) -> None:
    """Remove cell background so the cell is plain white."""
    tc_pr = cell._tc.get_or_add_tcPr()
    existing = tc_pr.find(qn("w:shd"))
    if existing is not None:
        tc_pr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "auto")
    tc_pr.append(shd)


def _apply_banded_rows(table, band_color: str = "F2F2F2") -> None:
    row_count = len(table.rows)
    col_count = len(table.columns) if table.rows else 0
    for r_idx in range(row_count):
        if r_idx == 0 or r_idx % 2 == 0:
            continue
        for c_idx in range(col_count):
            _set_cell_shading(table.cell(r_idx, c_idx), band_color)


def _set_cell_alignment(cell, align: str) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    mapping = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    target = mapping.get((align or "left").lower(), WD_ALIGN_PARAGRAPH.LEFT)
    for para in cell.paragraphs:
        para.alignment = target


def _set_cell_margins(cell, top: int, bot: int, left: int, right: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    existing = tc_pr.find(qn("w:tcMar"))
    if existing is not None:
        tc_pr.remove(existing)
    mar = OxmlElement("w:tcMar")
    for name, val in (
        ("top", top),
        ("left", left),
        ("bottom", bot),
        ("right", right),
    ):
        el = OxmlElement(f"w:{name}")
        el.set(qn("w:w"), str(max(0, int(val))))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tc_pr.append(mar)


def _set_repeat_header(table) -> None:
    if not table.rows:
        return
    tr = table.rows[0]._tr
    tr_pr = tr.get_or_add_trPr()
    existing = tr_pr.find(qn("w:tblHeader"))
    if existing is None:
        hdr = OxmlElement("w:tblHeader")
        tr_pr.append(hdr)


def _set_table_width_percent(table, percent: int) -> None:
    tbl_pr = _ensure_tbl_pr(table)
    existing = tbl_pr.find(qn("w:tblW"))
    if existing is not None:
        tbl_pr.remove(existing)
    pct = max(10, min(100, int(percent)))
    # Word stores percent as fiftieths of a percent
    w = OxmlElement("w:tblW")
    w.set(qn("w:w"), str(pct * 50))
    w.set(qn("w:type"), "pct")
    tbl_pr.append(w)


def _set_table_spacing(table, before_pt: float, after_pt: float) -> None:
    """Approximate spacing via table cell margins on first/last rows is hard;
    set tblCellMar defaults instead when provided as layout spacing."""
    tbl_pr = _ensure_tbl_pr(table)
    # Store as doc-level hint via tblLook / no dedicated spacing — apply as
    # paragraph spacing on an empty spacer isn't reliable. Use tblCellMar bump.
    _ = (before_pt, after_pt, tbl_pr)  # reserved for future OOXML spacing


def _cell_looks_numeric(text: str) -> bool:
    t = (text or "").strip().replace(",", "").replace("%", "")
    if not t:
        return False
    try:
        float(t)
        return True
    except ValueError:
        return False


def _column_is_numeric(table, col_idx: int) -> bool:
    values = []
    for r_idx, row in enumerate(table.rows):
        if r_idx == 0:
            continue
        if col_idx >= len(row.cells):
            continue
        text = (row.cells[col_idx].text or "").strip()
        if text:
            values.append(text)
    if not values:
        return False
    numeric = sum(1 for v in values if _cell_looks_numeric(v))
    return numeric >= max(1, int(0.7 * len(values)))


def _empty_cell_percent(table) -> float:
    total = 0
    empty = 0
    row_count = len(table.rows)
    col_count = len(table.columns) if table.rows else 0
    seen_tcs: List[Any] = []
    for r_idx in range(row_count):
        for c_idx in range(col_count):
            cell = table.cell(r_idx, c_idx)
            tc = cell._tc
            if any(tc is x for x in seen_tcs):
                continue
            seen_tcs.append(tc)
            total += 1
            if not (cell.text or "").strip():
                empty += 1
    if total == 0:
        return 0.0
    return 100.0 * empty / total


def _find_empty_cells(table) -> List[Dict[str, int]]:
    """Return unique empty cells as {row, col} (0-based).

    Uses table.cell(r, c) and identity (`is`) for merge dedupe — id() is
    unreliable because python-docx recycles wrapper objects.
    """
    empty: List[Dict[str, int]] = []
    seen_tcs: List[Any] = []
    row_count = len(table.rows)
    col_count = len(table.columns) if table.rows else 0
    for r_idx in range(row_count):
        for c_idx in range(col_count):
            cell = table.cell(r_idx, c_idx)
            tc = cell._tc
            if any(tc is x for x in seen_tcs):
                continue
            seen_tcs.append(tc)
            if not (cell.text or "").strip():
                empty.append({"row": r_idx, "col": c_idx})
    return empty


def fill_table_cell(
    doc,
    *,
    table_index: int,
    row: int,
    col: int,
    text: str,
    font_name: str = "Times New Roman",
    font_size: int = 12,
) -> Dict[str, Any]:
    """Write text into a specific table cell. Returns updated cell info."""
    if table_index < 0 or table_index >= len(doc.tables):
        raise ValueError(f"table_index {table_index} out of range")
    table = doc.tables[table_index]
    if _element_is_before_body_start(doc, table._tbl):
        raise ValueError("Cannot edit tables on the cover / project-info pages")
    row_count = len(table.rows)
    col_count = len(table.columns) if table.rows else 0
    if row < 0 or row >= row_count:
        raise ValueError(f"row {row} out of range")
    if col < 0 or col >= col_count:
        raise ValueError(f"col {col} out of range")

    cell = table.cell(row, col)
    value = (text or "").strip()
    # Clear existing paragraph content, then write one styled run
    if cell.paragraphs:
        first = cell.paragraphs[0]
        for p in list(cell.paragraphs)[1:]:
            parent = p._element.getparent()
            if parent is not None:
                parent.remove(p._element)
        for child in list(first._element):
            if child.tag != qn("w:pPr"):
                first._element.remove(child)
        run = first.add_run(value)
        # Style via shared helper (re-apply to whole cell)
        _apply_cell_font(cell, font_name, int(font_size), bold=False)
    else:
        cell.text = value
        _apply_cell_font(cell, font_name, int(font_size), bold=False)

    return {
        "table_index": table_index,
        "row": row,
        "col": col,
        "text": value,
        "filled": True,
        "font_name": font_name,
        "font_size": int(font_size),
    }


def format_table(table, rules: Dict[str, Any]) -> Dict[str, Any]:
    """Apply visual table_style rules. Returns notes/warnings for the caller."""
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.shared import Twips

    notes: List[str] = []
    font_name = str(rules.get("font_name", "Times New Roman"))
    font_size = int(rules.get("font_size", 12))
    wide = str(rules.get("wide_table_handling") or "flag_for_manual_review")
    col_count = len(table.columns) if table.rows else 0

    if wide == "shrink_font" and col_count >= 6:
        font_size = max(8, font_size - 2)
        notes.append("wide_table_shrink_font")
    elif wide == "flag_for_manual_review" and col_count >= 8:
        notes.append("wide_table_flag_for_manual_review")
    elif wide == "landscape_page" and col_count >= 8:
        notes.append("wide_table_landscape_suggested")

    max_empty = float(rules.get("max_empty_cell_percent", 30) or 30)
    empty_pct = _empty_cell_percent(table)
    if empty_pct > max_empty:
        notes.append(f"empty_cells_{empty_pct:.0f}pct_exceeds_{max_empty:.0f}")

    try:
        table.style = "Table Grid"
    except Exception:
        pass

    header_bg = str(rules.get("header_bg", "FFFFFF"))
    header_shading = bool(rules.get("header_row_shading", False))
    banded = bool(rules.get("banded_rows", False))
    header_fill = header_bg.replace("#", "").strip().upper()
    band_color = str(rules.get("band_color", "F2F8FC")).replace("#", "").strip().upper()

    # Previous stock defaults (banded + pale blue) → treat as "no color"
    if banded and band_color in ("F2F8FC", "F2F2F2", "D6E4F0", "FFFFFF", "AUTO"):
        banded = False
    apply_header_fill = (
        header_shading
        and header_fill not in ("", "FFFFFF", "AUTO", "NONE", "D6E4F0", "F2F8FC")
    )

    # Kill Word style-driven banding / first-row tint, then wipe cell fills
    _set_tbl_look(table, header_shading=apply_header_fill, banded=banded)
    _clear_all_table_shading(table)

    page_align = str(rules.get("alignment_on_page") or "").strip().lower()
    center = rules.get("center_table", True) if not page_align else page_align == "center"
    try:
        table.alignment = (
            WD_TABLE_ALIGNMENT.CENTER if center else WD_TABLE_ALIGNMENT.LEFT
        )
    except Exception:
        pass

    border_style = str(rules.get("border_style") or "").strip().lower()
    if not border_style:
        border_style = "academic_standard" if rules.get("borders", True) else "none"
    thickness = int(rules.get("border_thickness", rules.get("border_size", 4)) or 4)
    border_color = str(rules.get("border_color", "000000"))
    if border_style != "none" and rules.get("borders", True):
        _set_table_borders(
            table,
            border_style=border_style,
            color=border_color,
            size=thickness,
        )
    elif border_style == "none" or not rules.get("borders", True):
        _set_table_borders(table, border_style="none", size=0)

    max_w = int(rules.get("max_width_percent", 100) or 100)
    _set_table_width_percent(table, max_w)

    pad_t = int(rules.get("cell_padding_top", 60) or 60)
    pad_b = int(rules.get("cell_padding_bot", 60) or 60)
    pad_l = int(rules.get("cell_padding_lft", 108) or 108)
    pad_r = int(rules.get("cell_padding_rgt", 108) or 108)

    header_align = str(rules.get("header_align", "center"))
    text_align = str(
        rules.get("text_column_alignment")
        or rules.get("body_align")
        or "left"
    )
    numeric_align = str(
        rules.get("numeric_column_alignment") or text_align or "left"
    )
    # Bold header ONLY when the template explicitly enables it
    header_bold = bool(rules.get("header_bold", False))

    legacy_numeric_default = (
        numeric_align.lower() == "right" and text_align.lower() == "left"
    )
    use_numeric_split = (
        numeric_align.lower() != text_align.lower() and not legacy_numeric_default
    )
    numeric_cols: Set[int] = set()
    if use_numeric_split and table.rows and col_count:
        for c in range(col_count):
            if _column_is_numeric(table, c):
                numeric_cols.add(c)

    row_count = len(table.rows)
    for r_idx in range(row_count):
        is_header = r_idx == 0
        for c_idx in range(col_count):
            cell = table.cell(r_idx, c_idx)
            _apply_cell_font(
                cell,
                font_name,
                font_size,
                bold=header_bold if is_header else False,
            )
            _set_cell_margins(cell, pad_t, pad_b, pad_l, pad_r)
            if is_header:
                _set_cell_alignment(cell, header_align)
                if apply_header_fill:
                    _set_cell_shading(cell, header_fill)
                else:
                    _clear_cell_shading(cell)
            else:
                if use_numeric_split and c_idx in numeric_cols:
                    align = numeric_align
                else:
                    align = text_align
                _set_cell_alignment(cell, align)
                if not banded:
                    _clear_cell_shading(cell)

    if banded:
        _apply_banded_rows(table, band_color)

    if rules.get("repeat_header", True):
        _set_repeat_header(table)

    if rules.get("row_height_policy") == "fixed_minimum" and table.rows:
        from docx.oxml.ns import qn as _qn

        min_h = Twips(240)  # ~12pt
        for row in table.rows:
            tr = row._tr
            tr_pr = tr.get_or_add_trPr()
            tr_h = tr_pr.find(_qn("w:trHeight"))
            if tr_h is None:
                tr_h = OxmlElement("w:trHeight")
                tr_pr.append(tr_h)
            tr_h.set(_qn("w:val"), str(int(min_h)))
            tr_h.set(_qn("w:hRule"), "atLeast")

    if rules.get("auto_fit", True):
        tbl_pr = _ensure_tbl_pr(table)
        layout = tbl_pr.find(qn("w:tblLayout"))
        if layout is None:
            layout = OxmlElement("w:tblLayout")
            tbl_pr.append(layout)
        layout.set(qn("w:type"), "autofit")

    _set_table_spacing(
        table,
        float(rules.get("space_before", 6) or 6),
        float(rules.get("space_after", 6) or 6),
    )

    return {"notes": notes, "empty_cell_percent": empty_pct, "col_count": col_count}


def format_tables_in_document(
    doc,
    selected_indices: Optional[Set[int]] = None,
    *,
    preset: str = "academic",
    custom_rules: Optional[Dict[str, Any]] = None,
    template_rules: Optional[Dict[str, Any]] = None,
    add_captions: bool = True,
    formatting_rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply table formatting and optional captions to selected tables."""
    from services.table_config import get_table_format_config, merge_table_style

    if formatting_rules:
        cfg = get_table_format_config(formatting_rules)
        rules = dict(cfg["table_style"])
        if custom_rules:
            rules.update(custom_rules)
        rules = merge_table_style(rules)
    else:
        rules = _merge_table_rules(preset, custom_rules, template_rules)
        rules = merge_table_style(rules)

    formatted: List[int] = []
    style_notes: List[Dict[str, Any]] = []

    if add_captions:
        if formatting_rules:
            from services.table_numbering_service import (
                apply_numbering_to_table_captions,
                assign_table_numbers,
            )

            assignments = assign_table_numbers(doc, formatting_rules)
            apply_numbering_to_table_captions(doc, assignments, formatting_rules)
        else:
            ensure_table_captions(doc)

    for index, table in enumerate(doc.tables):
        if selected_indices is not None and index not in selected_indices:
            continue
        if _element_is_before_body_start(doc, table._tbl):
            continue
        info = format_table(table, rules) or {}
        formatted.append(index)
        if info.get("notes"):
            style_notes.append({"index": index, "notes": info["notes"]})

    return {
        "formatted_tables": formatted,
        "formatted_count": len(formatted),
        "rules_applied": rules,
        "style_notes": style_notes,
    }
