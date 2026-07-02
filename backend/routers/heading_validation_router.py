"""
routers/heading_validation.py
──────────────────────────────
POST /api/validate-headings

Upload a document + send required sections → get back which sections
were found, which are missing, and which layer matched each one.
"""

from __future__ import annotations

import uuid
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from services.document_block_extractor import extract_blocks
from services.heading_normalizer import match_document_headings

router     = APIRouter(prefix="/api", tags=["Layer 2 – Heading Validation"])
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED    = {".docx", ".pdf", ".txt"}


@router.post("/validate-headings", summary="Match document headings against required sections")
async def validate_headings(
    file: UploadFile = File(...),
    required_sections: str = Form(
        ...,
        description='Comma-separated list, e.g. "Introduction,Methodology,Results,Conclusion"',
    ),
    fuzzy_threshold: float = Form(80.0),
    semantic_threshold: float = Form(0.75),
    use_semantic: bool = Form(True),
) -> JSONResponse:
    """
    Full Layer 1 + Layer 2 pipeline in one call:

    1. Parses the uploaded document into typed blocks (Layer 1)
    2. Extracts heading texts
    3. Runs 4-layer synonym matching against `required_sections` (Layer 2)

    Returns a detailed match report showing which layer matched each heading.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type '{suffix}'.")

    required = [s.strip() for s in required_sections.split(",") if s.strip()]
    if not required:
        raise HTTPException(400, "required_sections must not be empty.")

    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    try:
        with temp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        # Layer 1
        blocks   = extract_blocks(str(temp_path))
        headings = [b["text"] for b in blocks if b["type"] == "heading"]

        # Layer 2
        report = match_document_headings(
            extracted_headings = headings,
            required_sections  = required,
            fuzzy_threshold    = fuzzy_threshold,
            semantic_threshold = semantic_threshold,
            use_semantic       = use_semantic,
        )

    except Exception as exc:
        raise HTTPException(500, str(exc))
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return JSONResponse(content={
        "filename":          file.filename,
        "extracted_headings": headings,
        **report,
    })