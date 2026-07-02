"""
routers/block_extraction.py
────────────────────────────
POST /api/extract-blocks

Accepts a .docx / .pdf / .txt file upload and returns the Layer-1
typed JSON block list.  All higher layers (heading matching, structure
check, style check) call this first.
"""

from __future__ import annotations

import os
import uuid
import shutil
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from services.document_block_extractor import extract_blocks

router = APIRouter(prefix="/api", tags=["Layer 1 – Block Extraction"])

# Temp directory for uploaded files (already exists in your project)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}


@router.post("/extract-blocks", summary="Parse document into typed JSON blocks")
async def extract_document_blocks(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload a .docx, .pdf, or .txt file.

    Returns a JSON object:
    ```json
    {
        "filename": "report.docx",
        "total_blocks": 42,
        "blocks": [
            {"type": "heading", "text": "Introduction", "level": 1, "index": 0, "metadata": {...}},
            {"type": "paragraph", "text": "This project ...", "level": null, "index": 1, "metadata": {...}},
            ...
        ],
        "summary": {
            "headings":    12,
            "paragraphs":  25,
            "list_items":   4,
            "tables":       1,
            "images":       0
        }
    }
    ```
    """
    # ── Validate extension ───────────────────────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # ── Save to temp file ────────────────────────────────────────────────────
    temp_name = f"{uuid.uuid4().hex}{suffix}"
    temp_path = UPLOAD_DIR / temp_name

    try:
        with temp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        # ── Extract blocks ───────────────────────────────────────────────────
        blocks: List[Dict[str, Any]] = extract_blocks(str(temp_path))

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()

    # ── Build summary ────────────────────────────────────────────────────────
    summary = {
        "headings":   sum(1 for b in blocks if b["type"] == "heading"),
        "paragraphs": sum(1 for b in blocks if b["type"] == "paragraph"),
        "list_items": sum(1 for b in blocks if b["type"] == "list_item"),
        "tables":     sum(1 for b in blocks if b["type"] == "table"),
        "images":     sum(1 for b in blocks if b["type"] == "image"),
    }

    return JSONResponse(content={
        "filename":     file.filename,
        "total_blocks": len(blocks),
        "blocks":       blocks,
        "summary":      summary,
    })


@router.post(
    "/extract-blocks/headings-only",
    summary="Return only heading blocks (useful for Layer 2 preview)",
)
async def extract_headings_only(file: UploadFile = File(...)) -> JSONResponse:
    """
    Same as /extract-blocks but returns ONLY heading blocks.
    Useful for quickly previewing heading structure before running
    the full synonym-matching pipeline in Layer 2.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix}'.")

    temp_name = f"{uuid.uuid4().hex}{suffix}"
    temp_path = UPLOAD_DIR / temp_name

    try:
        with temp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        blocks = extract_blocks(str(temp_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if temp_path.exists():
            temp_path.unlink()

    headings = [b for b in blocks if b["type"] == "heading"]

    return JSONResponse(content={
        "filename": file.filename,
        "total_headings": len(headings),
        "headings": headings,
    })