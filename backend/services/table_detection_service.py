"""
services/table_detection_service.py
=====================================
Detects and analyses ALL tables in a DOCX or PDF document.

For each table it reports:
  - Row/column counts
  - Whether a header row is present
  - Per-cell font metadata
  - Structural issues  (borders, alignment, font inconsistency, …)

Output shape per table
----------------------
{
    "index":          int,          # 0-based position in document
    "label":          str,          # "Table 1", "Table 2", …
    "row_count":      int,
    "col_count":      int,
    "has_header_row": bool,
    "issues":         [{"code": str, "message": str, "severity": str}, …],
    "preview_rows":   [[str, …], …],   # first 4 rows, truncated text
    "raw_rows":       [[str, …], …],   # all rows, full text
    "cell_meta":      [                # parallel to raw_rows
                         [{"bold":bool,"font_size":float|None,
                           "font_name":str|None,"alignment":str}, …],
                       ],
    "source":         "docx" | "pdf",
}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from lxml import etree

# ── XML namespaces (mirrors document_parser.py) ───────────────────────────────
NS = {
    "w":  "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r":  "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a":  "http://schemas.openxmlformats.org/drawingml/2006/main",
}

# Severity constants
_WARN  = "warning"
_ERROR = "error"
_INFO  = "info"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def detect_tables(file_path: str) -> List[Dict[str, Any]]:
    """
    Detect and analyse all tables in *file_path*.
    Supports .docx and .pdf.
    Returns a list of table-meta dicts (see module docstring).
    """
    if file_path.endswith(".docx"):
        return _detect_docx_tables(file_path)
    elif file_path.endswith(".pdf"):
        return _detect_pdf_tables(file_path)
    return []


# ─────────────────────────────────────────────────────────────────────────────
# DOCX  detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_docx_tables(file_path: str) -> List[Dict[str, Any]]:
    from docx import Document

    doc    = Document(file_path)
    result = []

    for idx, table in enumerate(doc.tables):
        meta = _analyse_docx_table(idx, table)
        result.append(meta)

    return result


def _analyse_docx_table(
    idx: int,
    table,
) -> Dict[str, Any]:
    """Deep-analyse one python-docx Table object."""

    rows: List[List[str]]                  = []
    cell_meta: List[List[Dict[str, Any]]]  = []

    for row in table.rows:
        row_texts: List[str]                  = []
        row_meta:  List[Dict[str, Any]]       = []

        for cell in row.cells:
            text = cell.text.strip()
            row_texts.append(text)

            # Per-cell font metadata — look at first non-empty run
            bold      = False
            font_size: Optional[float] = None
            font_name: Optional[str]   = None
            alignment = "left"

            for para in cell.paragraphs:
                # Alignment
                if para.paragraph_format.alignment is not None:
                    _a = para.paragraph_format.alignment
                    alignment = (getattr(_a, "name", None) or str(_a) or "left").lower()

                for run in para.runs:
                    if run.bold:
                        bold = True
                    if run.font.size and font_size is None:
                        font_size = round(run.font.size.pt, 1)
                    if run.font.name and font_name is None:
                        font_name = run.font.name
                    if bold and font_size and font_name:
                        break
                if bold and font_size and font_name:
                    break

            row_meta.append({
                "bold":      bold,
                "font_size": font_size,
                "font_name": font_name,
                "alignment": alignment,
            })

        rows.append(row_texts)
        cell_meta.append(row_meta)

    row_count = len(rows)
    col_count = max((len(r) for r in rows), default=0)

    has_header = _infer_header_row(rows, cell_meta)
    issues     = _check_docx_table_issues(table, rows, cell_meta, has_header)

    return {
        "index":          idx,
        "label":          f"Table {idx + 1}",
        "row_count":      row_count,
        "col_count":      col_count,
        "has_header_row": has_header,
        "issues":         issues,
        "preview_rows":   _preview(rows),
        "raw_rows":       rows,
        "cell_meta":      cell_meta,
        "source":         "docx",
    }


def _check_empty_cells(
    rows: List[List[str]],
) -> Dict[str, Any] | None:
    """Check for empty cells and return issue if any are found."""
    empty_cells = []
    
    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row):
            if not cell.strip():
                empty_cells.append({
                    "row": row_idx + 1,  # 1-based for readability
                    "column": col_idx + 1,
                    "location": f"Row {row_idx + 1}, Column {col_idx + 1}"
                })
    
    if empty_cells:
        cell_locations = ", ".join([cell["location"] for cell in empty_cells[:5]])
        if len(empty_cells) > 5:
            cell_locations += f", and {len(empty_cells) - 5} more..."

        issue = _issue(
            "EMPTY_CELLS_FOUND",
            f"Found {len(empty_cells)} empty cell(s): {cell_locations}. "
            "All cells must contain data.",
            _ERROR,
        )
        # Include structured cell locations so the frontend can offer "Add Text"
        issue["cells"] = empty_cells
        return issue
    return None


def _check_docx_table_issues(
    table,
    rows:      List[List[str]],
    cell_meta: List[List[Dict[str, Any]]],
    has_header: bool,
) -> List[Dict[str, Any]]:
    """Return a list of issue dicts for one DOCX table."""
    issues: List[Dict[str, Any]] = []
    w_ns = NS["w"]

    # ── 0. Empty cells ────────────────────────────────────────────────────────
    empty_cell_issue = _check_empty_cells(rows)
    if empty_cell_issue:
        issues.append(empty_cell_issue)

    # ── 1. Missing header row ─────────────────────────────────────────────────
    if not has_header and len(rows) > 1:
        issues.append(_issue(
            "NO_HEADER_ROW",
            "Table has no detectable header row (no bold / no heading style).",
            _WARN,
        ))

    # ── 2. Missing or inconsistent borders ───────────────────────────────────
    tbl_el = table._tbl
    tblPr  = tbl_el.find(f"{{{w_ns}}}tblPr")
    tblBorders = tblPr.find(f"{{{w_ns}}}tblBorders") if tblPr is not None else None

    if tblBorders is None:
        issues.append(_issue(
            "NO_BORDERS",
            "Table has no explicit border definition — borders may be invisible.",
            _WARN,
        ))
    else:
        border_tags = [
            "top", "bottom", "left", "right", "insideH", "insideV",
        ]
        missing_borders = [
            tag for tag in border_tags
            if tblBorders.find(f"{{{w_ns}}}{tag}") is None
        ]
        if missing_borders:
            issues.append(_issue(
                "INCOMPLETE_BORDERS",
                f"Some border sides are undefined: {', '.join(missing_borders)}.",
                _INFO,
            ))

    # ── 3. Inconsistent font sizes across body cells ──────────────────────────
    body_start = 1 if has_header else 0
    body_sizes = [
        m["font_size"]
        for row_meta in cell_meta[body_start:]
        for m in row_meta
        if m["font_size"] is not None
    ]
    if body_sizes:
        unique_sizes = set(body_sizes)
        if len(unique_sizes) > 1:
            issues.append(_issue(
                "INCONSISTENT_FONT_SIZE",
                f"Body cells use multiple font sizes: "
                f"{sorted(unique_sizes)}pt — standardise to one size.",
                _WARN,
            ))

    # ── 4. Inconsistent font names ────────────────────────────────────────────
    body_fonts = [
        m["font_name"]
        for row_meta in cell_meta[body_start:]
        for m in row_meta
        if m["font_name"] is not None
    ]
    if body_fonts:
        unique_fonts = set(body_fonts)
        if len(unique_fonts) > 1:
            issues.append(_issue(
                "INCONSISTENT_FONT_NAME",
                f"Body cells use multiple fonts: "
                f"{', '.join(sorted(unique_fonts))} — standardise to one font.",
                _WARN,
            ))

    # ── 5. Alignment issues ───────────────────────────────────────────────────
    body_alignments = [
        m["alignment"]
        for row_meta in cell_meta[body_start:]
        for m in row_meta
    ]
    if body_alignments:
        unique_align = set(body_alignments)
        if len(unique_align) > 1:
            issues.append(_issue(
                "ALIGNMENT_INCONSISTENCY",
                f"Body cells use mixed alignments: "
                f"{', '.join(sorted(unique_align))}.",
                _INFO,
            ))

    # ── 6. Uneven column widths ───────────────────────────────────────────────
    tblGrid = tbl_el.find(f"{{{w_ns}}}tblGrid")
    if tblGrid is not None:
        col_widths = [
            int(gc.get(f"{{{w_ns}}}w", 0))
            for gc in tblGrid.findall(f"{{{w_ns}}}gridCol")
            if gc.get(f"{{{w_ns}}}w")
        ]
        if col_widths:
            width_range = max(col_widths) - min(col_widths)
            if width_range > 500:          # 500 twips ≈ 0.35 inch
                issues.append(_issue(
                    "UNEVEN_COLUMN_WIDTHS",
                    f"Column widths vary by {width_range} twips "
                    f"(min={min(col_widths)}, max={max(col_widths)}). "
                    "Consider uniform column widths.",
                    _INFO,
                ))

    # ── 7. Empty cells ────────────────────────────────────────────────────────
    empty_count = sum(
        1 for row in rows for cell in row if not cell.strip()
    )
    total_cells = sum(len(row) for row in rows)
    if total_cells > 0 and empty_count / total_cells > 0.3:
        issues.append(_issue(
            "MANY_EMPTY_CELLS",
            f"{empty_count}/{total_cells} cells are empty "
            f"({int(empty_count/total_cells*100)}%). "
            "Check for merged cells or incomplete data.",
            _INFO,
        ))

    # ── 8. Header row not bold ────────────────────────────────────────────────
    if has_header and cell_meta:
        header_bolds = [m["bold"] for m in cell_meta[0]]
        if not any(header_bolds):
            issues.append(_issue(
                "HEADER_NOT_BOLD",
                "Header row text is not bold — consider formatting it bold "
                "to distinguish it from body rows.",
                _WARN,
            ))

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# PDF detection  (via pdfplumber)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_pdf_tables(file_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError:
        print("[TableDetector] pdfplumber not installed — PDF table detection skipped.")
        return []

    result = []
    global_idx = 0

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_data in tables:
                if not table_data:
                    continue

                rows = [
                    [str(cell).strip() if cell else "" for cell in row]
                    for row in table_data
                ]
                row_count = len(rows)
                col_count = max((len(r) for r in rows), default=0)

                # Build dummy cell_meta (no font info in pdfplumber basic mode)
                cell_meta = [
                    [{"bold": False, "font_size": None,
                      "font_name": None, "alignment": "left"}
                     for _ in row]
                    for row in rows
                ]

                has_header = _infer_header_row(rows, cell_meta)
                issues     = _check_pdf_table_issues(rows, has_header, page_num)

                result.append({
                    "index":          global_idx,
                    "label":          f"Table {global_idx + 1}",
                    "row_count":      row_count,
                    "col_count":      col_count,
                    "has_header_row": has_header,
                    "issues":         issues,
                    "preview_rows":   _preview(rows),
                    "raw_rows":       rows,
                    "cell_meta":      cell_meta,
                    "source":         "pdf",
                    "page":           page_num,
                })
                global_idx += 1

    return result


def _check_pdf_table_issues(
    rows: List[List[str]],
    has_header: bool,
    page_num: int,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []

    # ── Empty cells ───────────────────────────────────────────────────────────
    empty_cell_issue = _check_empty_cells(rows)
    if empty_cell_issue:
        # Customize message for PDF
        issues.append(_issue(
            "EMPTY_CELLS_FOUND",
            f"Found empty cell(s) on page {page_num}: {empty_cell_issue['message'].split(': ')[1]}",
            _ERROR,
        ))

    if not has_header and len(rows) > 1:
        issues.append(_issue(
            "NO_HEADER_ROW",
            f"PDF table on page {page_num} has no detectable header row.",
            _WARN,
        ))

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _infer_header_row(
    rows:      List[List[str]],
    cell_meta: List[List[Dict[str, Any]]],
) -> bool:
    """Heuristically decide whether row 0 is a header."""
    if not rows or not cell_meta:
        return False

    first_row_meta = cell_meta[0]

    # Bold cells in row 0
    if any(m["bold"] for m in first_row_meta):
        return True

    # All-caps short text in row 0
    texts = rows[0]
    if texts and all(
        t.isupper() and len(t.split()) <= 5
        for t in texts if t.strip()
    ):
        return True

    # Row 0 has no digits while body rows do (common in data tables)
    if len(rows) > 1:
        header_has_digits = any(
            any(ch.isdigit() for ch in t) for t in texts
        )
        body_has_digits = any(
            any(ch.isdigit() for ch in cell)
            for row in rows[1:]
            for cell in row
        )
        if not header_has_digits and body_has_digits:
            return True

    return False


def _preview(rows: List[List[str]], max_rows: int = 4, max_len: int = 40) -> List[List[str]]:
    """Return first *max_rows* rows with cell text truncated."""
    preview = []
    for row in rows[:max_rows]:
        preview.append([
            (cell[:max_len] + "…") if len(cell) > max_len else cell
            for cell in row
        ])
    return preview


def _issue(code: str, message: str, severity: str) -> Dict[str, Any]:
    return {"code": code, "message": message, "severity": severity}


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

class TableDetectionService:
    """Thin wrapper so routers can use DI-style access."""

    def detect(self, file_path: str) -> List[Dict[str, Any]]:
        return detect_tables(file_path)


table_detection_service = TableDetectionService()
