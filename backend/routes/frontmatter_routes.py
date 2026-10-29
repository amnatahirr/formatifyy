"""
frontmatter_routes.py — Cover / project-info page analyze & generate endpoints.

POST /api/documents/{document_id}/frontmatter/analyze
POST /api/documents/{document_id}/frontmatter/generate
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from database import get_db
from frontmatter.frontmatter_data import build_frontmatter_context
from frontmatter.frontmatter_detector import detect_frontmatter
from frontmatter.frontmatter_generator import generate_frontmatter_docx, scaffold_templates
from models import DetectionResult, FrontmatterGenerateRequest

router = APIRouter(prefix="/api/documents", tags=["Frontmatter"])

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"


def _working_copy_path(document_id: int) -> str:
    return os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")


def _export_copy_path(document_id: int) -> str:
    return os.path.join(OUTPUT_DIR, f"export_{document_id}.docx")


def _require_owned_document(document_id: int, user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        )
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        return doc
    finally:
        conn.close()


def _resolve_docx_path(doc) -> str:
    """Prefer the formatted working copy; fall back to the uploaded file."""
    working = _working_copy_path(doc["id"])
    if os.path.exists(working):
        return working
    path = doc["file_path"]
    if path and os.path.exists(path) and str(path).lower().endswith(".docx"):
        return path
    raise HTTPException(
        status_code=400,
        detail="No DOCX available for this document. Upload/format a .docx first.",
    )


def _ai_client():
    gemini = (os.getenv("GEMINI_API_KEY") or "").strip()
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if gemini:
        from gemini_adapter import GeminiClientAdapter
        return GeminiClientAdapter(api_key=gemini)
    if anthropic_key:
        import anthropic
        return anthropic.AsyncAnthropic(api_key=anthropic_key)
    return None


def _load_detection(doc) -> Optional[DetectionResult]:
    raw = None
    try:
        raw = doc["frontmatter_detection"]
    except (KeyError, IndexError):
        raw = None
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return DetectionResult.model_validate(data)
    except Exception:
        return None


def _save_detection(document_id: int, result: DetectionResult) -> None:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE documents
            SET frontmatter_detection = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (result.model_dump_json(), document_id),
        )
        conn.commit()
    finally:
        conn.close()


def _persist_generate_meta(
    document_id: int,
    *,
    group_id: Optional[int],
    domains: Optional[list],
    signature_path: Optional[str],
) -> None:
    conn = get_db()
    cursor = conn.cursor()
    try:
        if group_id is not None:
            cursor.execute(
                "UPDATE documents SET group_id = ? WHERE id = ?",
                (group_id, document_id),
            )
        if domains is not None:
            cursor.execute(
                "UPDATE documents SET frontmatter_domains = ? WHERE id = ?",
                (json.dumps(list(domains)), document_id),
            )
        if signature_path is not None:
            cursor.execute(
                "UPDATE documents SET signature_path = ? WHERE id = ?",
                (signature_path, document_id),
            )
        cursor.execute(
            "UPDATE documents SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (document_id,),
        )
        conn.commit()
    finally:
        conn.close()


@router.post("/{document_id}/frontmatter/analyze")
async def analyze_frontmatter(
    document_id: int,
    user_id: int = Query(...),
):
    """
    Detect whether the first pages already contain a cover and/or project-info page.
    Persists DetectionResult JSON on documents.frontmatter_detection.
    Does not generate pages.
    """
    doc = _require_owned_document(document_id, user_id)
    docx_path = _resolve_docx_path(doc)

    client = _ai_client()
    result = await detect_frontmatter(docx_path, client=client)
    _save_detection(document_id, result)

    return {
        "document_id": document_id,
        "detection": result.model_dump(),
        "cover_status": "found" if result.cover_page_present else "missing",
        "info_status": "found" if result.info_page_present else "missing",
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/{document_id}/frontmatter/generate")
async def generate_frontmatter(
    document_id: int,
    user_id: int = Query(...),
    payload: FrontmatterGenerateRequest = Body(default_factory=FrontmatterGenerateRequest),
):
    """
    Generate missing cover and/or project-info pages using the last analyze result
    (partial generation). Merges into the working DOCX and updates the export copy.
    """
    doc = _require_owned_document(document_id, user_id)
    docx_path = _resolve_docx_path(doc)

    detection = _load_detection(doc)
    if detection is None:
        # Run analyze once if never persisted
        client = _ai_client()
        detection = await detect_frontmatter(docx_path, client=client)
        _save_detection(document_id, detection)

    insert_cover = (
        bool(payload.generate_cover)
        if payload.generate_cover is not None
        else (not detection.cover_page_present)
    )
    insert_info = (
        bool(payload.generate_info)
        if payload.generate_info is not None
        else (not detection.info_page_present)
    )

    if not insert_cover and not insert_info:
        return {
            "document_id": document_id,
            "generated_cover": False,
            "generated_info": False,
            "message": "Nothing to generate — cover and info pages already present.",
            "detection": detection.model_dump(),
            "download_url": f"/api/format-document/export/{document_id}?user_id={user_id}&format=docx",
            "preview_url": f"/api/format-document/from-document/{document_id}?user_id={user_id}",
        }

    _persist_generate_meta(
        document_id,
        group_id=payload.group_id,
        domains=payload.domains,
        signature_path=payload.signature_path,
    )

    try:
        ctx = build_frontmatter_context(
            document_id,
            group_id=payload.group_id,
            domains=payload.domains,
            signature_path=payload.signature_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    scaffold_templates()
    try:
        merged = generate_frontmatter_docx(
            docx_path,
            ctx,
            insert_cover=insert_cover,
            insert_info=insert_info,
        )
    except Exception as exc:
        print(f"[frontmatter] generate failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Frontmatter generation failed: {exc}",
        ) from exc

    working = _working_copy_path(document_id)
    os.makedirs(os.path.dirname(working), exist_ok=True)
    with open(working, "wb") as f:
        f.write(merged)

    export_path = _export_copy_path(document_id)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    shutil.copy2(working, export_path)

    # Refresh detection to reflect inserted pages
    try:
        client = _ai_client()
        refreshed = await detect_frontmatter(working, client=client)
        _save_detection(document_id, refreshed)
        detection = refreshed
    except Exception as exc:
        print(f"[frontmatter] post-generate re-analyze skipped: {exc}")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        updated = cursor.fetchone()
    finally:
        conn.close()

    meta: dict[str, Any] = {
        "id": document_id,
        "filename": updated["filename"] if updated else doc["filename"],
        "status": updated["status"] if updated else doc["status"],
        "group_id": updated["group_id"] if updated and "group_id" in updated.keys() else None,
        "updated_at": updated["updated_at"] if updated else None,
    }

    return {
        "document_id": document_id,
        "generated_cover": insert_cover,
        "generated_info": insert_info,
        "context_used": ctx.model_dump(),
        "detection": detection.model_dump(),
        "document": meta,
        "download_url": f"/api/format-document/export/{document_id}?user_id={user_id}&format=docx",
        "preview_url": f"/api/format-document/from-document/{document_id}?user_id={user_id}",
        "message": (
            "Generated "
            + " and ".join(
                [p for p, on in (("cover page", insert_cover), ("project info page", insert_info)) if on]
            )
            + " and prepended to the report."
        ),
    }
