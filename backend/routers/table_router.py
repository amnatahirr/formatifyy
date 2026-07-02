"""
routers/table_router.py
========================
Endpoints:
  GET  /api/tables/detect/{document_id}          — detect + analyse all tables
  POST /api/tables/format/{document_id}          — format selected tables (preset OR custom_rules)
  POST /api/tables/format-with-template/{document_id}
                                                 — format ALL detected tables using
                                                   the template's saved table_style
  GET  /api/tables/presets                       — return available preset configs
  GET  /api/tables/download/{document_id}        — download working copy

Follows the same patterns as routers/formatting.py and routers/documents.py:
  - get_db() for DB access
  - _working_copy_path() / _get_effective_path() for incremental edits
  - FileResponse for download
  - [v0] debug prints
"""

from __future__ import annotations

import os
import shutil
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from database import get_db
from services.table_detection_service import table_detection_service
from services.table_formatter_service import table_formatter_service, PRESETS

router = APIRouter(prefix="/api/tables", tags=["tables"])

UPLOAD_FOLDER  = "uploads"
WORKING_FOLDER = "uploads/working"
os.makedirs(UPLOAD_FOLDER,  exist_ok=True)
os.makedirs(WORKING_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Working-copy helpers  (mirror documents.py)
# ─────────────────────────────────────────────────────────────────────────────

def _working_copy_path(document_id: int) -> str:
    return os.path.join(WORKING_FOLDER, f"doc_{document_id}_working.docx")


def _get_effective_path(document_id: int, original_path: str) -> str:
    wc = _working_copy_path(document_id)
    return wc if os.path.exists(wc) else original_path


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────

class TableFormatRequest(BaseModel):
    selected_indices: List[int]
    preset:           str = "academic"
    custom_rules:     Optional[Dict[str, Any]] = None


class TableFormatWithTemplateRequest(BaseModel):
    """
    Format tables using the table_style saved inside a template's
    formatting_rules.  *selected_indices* is optional — if omitted,
    ALL detected tables are formatted.
    """
    template_id:      int
    selected_indices: Optional[List[int]] = None   # None → format all


class TableFillCellRequest(BaseModel):
    template_id: Optional[int] = None
    table_index: int
    row: int                 # 1-based
    column: int              # 1-based
    text: str


# ─────────────────────────────────────────────────────────────────────────────
# Helper: resolve template's table_style → custom_rules dict
# ─────────────────────────────────────────────────────────────────────────────

def _get_template_table_style(template_id: int) -> Dict[str, Any]:
    """
    Fetch the template from the DB and return its formatting_rules['table_style']
    dict.  Falls back to an empty dict if the key is missing.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT formatting_rules FROM templates WHERE id = ?",
            (template_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Template {template_id} not found.",
        )

    raw = row["formatting_rules"]
    if not raw:
        return {}

    try:
        rules = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return {}

    table_style = rules.get("table_style", {}) or {}

    # If the template didn't explicitly set table font, inherit from body settings
    # so tables follow the overall template typography by default.
    body_font = rules.get("body_font")
    body_size = rules.get("body_size")
    if body_font and not table_style.get("font_name"):
        table_style["font_name"] = body_font
    if body_size and not table_style.get("font_size"):
        table_style["font_size"] = body_size

    return table_style


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/tables/presets
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/presets")
def get_presets() -> JSONResponse:
    """Return the three built-in formatting preset configs."""
    return JSONResponse(content={
        name: {
            "name":        name.capitalize(),
            "description": _preset_description(name),
            "rules":       config,
        }
        for name, config in PRESETS.items()
    })


def _preset_description(name: str) -> str:
    return {
        "academic":     "Bold header, blue shading, banded rows, Times New Roman 12pt. "
                        "Ideal for research papers and reports.",
        "professional": "Dark navy header (white text), full borders, Calibri 11pt. "
                        "Clean and corporate.",
        "minimal":      "Thin grey borders only, no shading, Arial 11pt. "
                        "Lightweight and unobtrusive.",
    }.get(name, "")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/tables/detect/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/detect/{document_id}")
def detect_tables(
    document_id: int,
    user_id:     int = Query(...),
) -> JSONResponse:
    """
    Detect and analyse all tables in the document.
    Returns table metadata, issues, and cell previews.
    """
    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    file_path = _get_effective_path(document_id, doc["file_path"])

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".docx", ".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Table detection supports .docx and .pdf only (got {ext!r}).",
        )

    print(f"[TableDetect] document_id={document_id}  path={file_path}")

    tables = table_detection_service.detect(file_path)

    total_issues = sum(len(t["issues"]) for t in tables)
    print(f"[TableDetect] found {len(tables)} table(s), {total_issues} issue(s)")

    return JSONResponse(content={
        "document_id":   document_id,
        "filename":      doc["filename"],
        "total_tables":  len(tables),
        "total_issues":  total_issues,
        "tables":        tables,
        "summary": {
            "tables_with_issues": sum(1 for t in tables if t["issues"]),
            "clean_tables":       sum(1 for t in tables if not t["issues"]),
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/tables/format/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/format/{document_id}")
def format_tables(
    document_id: int,
    user_id:     int = Query(...),
    body:        TableFormatRequest = Body(...),
) -> JSONResponse:
    """
    Format ONLY the tables whose 0-based indices are in *selected_indices*.
    Uses a named preset (+ optional custom_rule overrides).
    Writes result to the per-document working copy so the original is preserved.
    """
    if not body.selected_indices:
        raise HTTPException(status_code=400, detail="selected_indices must not be empty.")

    valid_presets = list(PRESETS.keys())
    if body.preset not in valid_presets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid preset '{body.preset}'. Valid: {valid_presets}",
        )

    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    original_path = doc["file_path"]
    ext           = os.path.splitext(original_path)[1].lower()

    if ext != ".docx":
        raise HTTPException(
            status_code=400,
            detail="Table formatting currently supports .docx files only.",
        )

    source_path  = _get_effective_path(document_id, original_path)
    working_path = _working_copy_path(document_id)

    print(
        f"[TableFormat] document_id={document_id}  "
        f"indices={body.selected_indices}  preset={body.preset}  "
        f"source={source_path}"
    )

    success = table_formatter_service.apply_table_formatting(
        source_path      = source_path,
        output_path      = working_path,
        selected_indices = body.selected_indices,
        preset           = body.preset,
        custom_rules     = body.custom_rules,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Table formatting failed. Check server logs.",
        )

    print(f"[TableFormat] SUCCESS  working_copy={working_path}")

    return JSONResponse(content={
        "document_id":      document_id,
        "status":           "formatted",
        "formatted_tables": body.selected_indices,
        "preset":           body.preset,
        "working_copy":     working_path,
        "message": (
            f"{len(body.selected_indices)} table(s) formatted "
            f"with '{body.preset}' preset."
        ),
    })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/tables/format-with-template/{document_id}   ← NEW
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/format-with-template/{document_id}")
def format_tables_with_template(
    document_id: int,
    user_id:     int = Query(...),
    body:        TableFormatWithTemplateRequest = Body(...),
) -> JSONResponse:
    """
    Format tables in *document_id* using the table_style saved inside the
    specified template's formatting_rules.

    - If *selected_indices* is provided → only those tables are formatted.
    - If *selected_indices* is None     → ALL detected tables are formatted.

    This is the endpoint called from the user-facing document screen after
    the user has reviewed detected tables and clicks "Apply Template Style".
    """
    # ── 1. Authorise document access ──────────────────────────────────────
    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    original_path = doc["file_path"]
    ext           = os.path.splitext(original_path)[1].lower()

    if ext != ".docx":
        raise HTTPException(
            status_code=400,
            detail="Table formatting currently supports .docx files only.",
        )

    # ── 2. Load table_style from template ─────────────────────────────────
    table_style = _get_template_table_style(body.template_id)
    print(
        f"[TableFormat-Template] document_id={document_id}  "
        f"template_id={body.template_id}  "
        f"table_style_keys={list(table_style.keys())}"
    )

    if not table_style:
        print(
            f"[TableFormat-Template] WARNING: template {body.template_id} has "
            "no table_style — falling back to 'academic' preset."
        )

    # ── 3. Resolve which tables to format ─────────────────────────────────
    source_path  = _get_effective_path(document_id, original_path)
    working_path = _working_copy_path(document_id)

    selected_indices = body.selected_indices

    if selected_indices is None:
        # Detect all tables and format every one of them
        tables           = table_detection_service.detect(source_path)
        selected_indices = [t["index"] for t in tables]
        print(
            f"[TableFormat-Template] auto-selected all "
            f"{len(selected_indices)} table(s)"
        )

    if not selected_indices:
        return JSONResponse(content={
            "document_id":      document_id,
            "status":           "no_tables",
            "formatted_tables": [],
            "message":          "No tables found in document.",
        })

    # ── 4. Apply formatting ───────────────────────────────────────────────
    # table_style from the template IS the custom_rules dict the formatter
    # understands.  We pass preset="academic" as a safe base; the template
    # values will fully override every key they define.
    success = table_formatter_service.apply_table_formatting(
        source_path      = source_path,
        output_path      = working_path,
        selected_indices = selected_indices,
        preset           = "academic",       # base fallback
        custom_rules     = table_style or None,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Table formatting failed. Check server logs.",
        )

    print(
        f"[TableFormat-Template] SUCCESS  "
        f"tables={selected_indices}  working_copy={working_path}"
    )

    return JSONResponse(content={
        "document_id":      document_id,
        "status":           "formatted",
        "formatted_tables": selected_indices,
        "template_id":      body.template_id,
        "working_copy":     working_path,
        "message": (
            f"{len(selected_indices)} table(s) formatted "
            f"using template style (template_id={body.template_id})."
        ),
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/tables/download/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/download/{document_id}")
def download_formatted(
    document_id: int,
    user_id:     int = Query(...),
) -> FileResponse:
    """
    Download the working copy (with table formatting applied).
    Falls back to the original if no working copy exists.
    """
    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    serve_path = _get_effective_path(document_id, doc["file_path"])

    if not os.path.exists(serve_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path       = serve_path,
        filename   = doc["filename"],
        media_type = "application/vnd.openxmlformats-officedocument"
                     ".wordprocessingml.document",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/tables/fill-cell/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/fill-cell/{document_id}")
def fill_table_cell(
    document_id: int,
    user_id:     int = Query(...),
    body:        TableFillCellRequest = Body(...),
) -> JSONResponse:
    """
    Fill a specific table cell (1-based row/column) with provided text.
    Writes to the working copy so export/download includes the new content.

    If template_id is provided, re-apply the template table_style to that table
    so the inserted text matches the table formatting.
    """
    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    original_path = doc["file_path"]
    ext           = os.path.splitext(original_path)[1].lower()
    if ext != ".docx":
        raise HTTPException(
            status_code=400,
            detail="Filling table cells currently supports .docx files only.",
        )

    if body.row < 1 or body.column < 1:
        raise HTTPException(status_code=400, detail="row/column must be 1-based >= 1")
    if not (body.text or "").strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    source_path  = _get_effective_path(document_id, original_path)
    working_path = _working_copy_path(document_id)

    # Ensure we modify the working copy (preserve original)
    if source_path != working_path:
        shutil.copy2(source_path, working_path)

    # Fill the cell, then optionally re-format that table
    ok = table_formatter_service.fill_table_cell(
        docx_path   = working_path,
        table_index = body.table_index,
        row_1based  = body.row,
        col_1based  = body.column,
        text        = body.text,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to fill table cell.")

    if body.template_id is not None:
        table_style = _get_template_table_style(body.template_id)
        # Re-apply table formatting to this table only so inserted text matches style
        table_formatter_service.apply_table_formatting(
            source_path      = working_path,
            output_path      = working_path,
            selected_indices = [body.table_index],
            preset           = "academic",
            custom_rules     = table_style or None,
        )

    return JSONResponse(content={
        "document_id": document_id,
        "status":      "filled",
        "table_index": body.table_index,
        "row":         body.row,
        "column":      body.column,
        "message":     "Cell updated successfully.",
        "working_copy": working_path,
    })