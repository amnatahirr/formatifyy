"""New API routes for draft-template extraction from guideline DOCX files."""

from __future__ import annotations

import os

import anthropic
from fastapi import APIRouter, File, HTTPException, UploadFile

from config import ANALYSIS_MODEL
from template_extract import extract_template_draft_from_docx

router = APIRouter(prefix="/api/admin/templates", tags=["Admin"])


@router.post("/extract-from-document")
async def extract_template_from_document(
    file: UploadFile = File(...),
):
    """
    Upload a .docx that states formatting rules in prose.
    Returns a draft {name, description, required_sections, formatting_rules}
    matching the existing Create Template form shape. Does not save a template.
    """
    filename = file.filename or "upload.docx"
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured on the server",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        draft = await extract_template_draft_from_docx(client, raw, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Template extraction failed: {exc}",
        ) from exc

    return {
        "status": "ok",
        "model": ANALYSIS_MODEL,
        "draft": draft,
    }
