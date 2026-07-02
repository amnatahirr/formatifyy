"""
routers/structure_check.py
───────────────────────────
POST /api/check-structure

Upload a document + provide a template_id → full Layer 1 + 2 + 3 pipeline
returns a structure validation report.
"""

from __future__ import annotations

import uuid
import shutil
import json
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse

from services.document_block_extractor import extract_blocks
from services.structure_checker import check_structure
from database import get_db

router     = APIRouter(prefix="/api", tags=["Layer 3 – Structure Check"])
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED    = {".docx", ".pdf", ".txt"}


def _migrate_sections(raw: list) -> list:
    """Convert old plain-string sections to new dict format (same as admin.py)."""
    if not raw:
        return []
    migrated = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            migrated.append({"name": item, "order": i + 1, "required": True})
        else:
            migrated.append({
                "name":     item.get("name", ""),
                "order":    item.get("order", i + 1),
                "required": item.get("required", True),
            })
    return migrated


@router.post(
    "/check-structure",
    summary="Full Layer 1+2+3 pipeline: parse document and check structure against template",
)
async def check_document_structure(
    file:        UploadFile = File(...),
    template_id: int        = Form(..., description="Template ID from the database"),
    use_semantic: bool      = Form(True),
) -> JSONResponse:
    """
    Runs the complete Layer 1 → 2 → 3 pipeline:

    1. **Layer 1** — parse document into typed blocks
    2. **Layer 2** — match headings using 4-layer synonym matcher
    3. **Layer 3** — compare against template's required sections

    Returns a full structure report with:
    - `status`: "pass" or "fail"
    - `score`: 0–100
    - `issues`: list of errors/warnings with codes
    - `section_results`: per-section match details
    - `summary`: counts of found/missing/wrong-order/empty sections
    """
    # ── Validate file ─────────────────────────────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type '{suffix}'.")

    # ── Load template from DB ─────────────────────────────────────────────────
    conn = get_db()
    template_row = conn.execute(
        "SELECT * FROM templates WHERE id = ?", (template_id,)
    ).fetchone()
    conn.close()

    if not template_row:
        raise HTTPException(404, f"Template {template_id} not found.")

    raw_sections      = json.loads(template_row["required_sections"])
    template_sections = _migrate_sections(raw_sections)
    template_name     = template_row["name"]

    # ── Save uploaded file temporarily ───────────────────────────────────────
    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    try:
        with temp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        # Layer 1 — parse blocks
        blocks = extract_blocks(str(temp_path))

    except Exception as exc:
        raise HTTPException(500, f"Document parsing failed: {exc}")
    finally:
        if temp_path.exists():
            temp_path.unlink()

    # Layer 2 + 3 — structure check
    try:
        report = check_structure(
            blocks            = blocks,
            template_sections = template_sections,
            use_semantic      = use_semantic,
        )
    except Exception as exc:
        raise HTTPException(500, f"Structure check failed: {exc}")

    return JSONResponse(content={
        "filename":      file.filename,
        "template_id":   template_id,
        "template_name": template_name,
        **report,
    })


@router.post(
    "/check-structure/from-blocks",
    summary="Layer 3 only — pass pre-parsed blocks + template_id",
)
async def check_structure_from_blocks(
    blocks:      list       = Form(...),
    template_id: int        = Form(...),
    use_semantic: bool      = Form(True),
) -> JSONResponse:
    """
    Skips Layer 1 — useful when you already have blocks from a previous
    /extract-blocks call and just want to re-run the structure check
    with a different template.
    """
    conn = get_db()
    template_row = conn.execute(
        "SELECT * FROM templates WHERE id = ?", (template_id,)
    ).fetchone()
    conn.close()

    if not template_row:
        raise HTTPException(404, f"Template {template_id} not found.")

    raw_sections      = json.loads(template_row["required_sections"])
    template_sections = _migrate_sections(raw_sections)

    try:
        report = check_structure(blocks, template_sections, use_semantic)
    except Exception as exc:
        raise HTTPException(500, str(exc))

    return JSONResponse(content={
        "template_id":   template_id,
        "template_name": template_row["name"],
        **report,
    })