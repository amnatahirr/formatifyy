"""
routers/content_check_router.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Exposes the ContentChecker to Flutter via:

    POST /api/content-check/{document_id}?user_id=<int>

Flutter calls:  $baseUrl/content-check/$documentId?user_id=$userId
  where baseUrl = http://host:8000/api

So the full path that arrives at FastAPI is:
    POST /api/content-check/{document_id}

Mount in main.py:
    from routers.content_check_router import router as content_check_router
    app.include_router(content_check_router, prefix="/api")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Lazy-import the checkers (already loaded by documents router at startup) ──
def _get_checkers():
    """
    Re-use the singleton instances that documents.py already created.
    Falls back to creating new ones if not available.
    """
    try:
        # documents.py stores these in its module namespace
        from routers import documents as doc_module
        return (
            getattr(doc_module, "_content_checker", None),
            getattr(doc_module, "_perfect_checker", None),
        )
    except Exception:
        return None, None


def _get_db():
    """Get the shared database helper used everywhere else."""
    try:
        from database import db          # adjust import to your project layout
        return db
    except ImportError:
        try:
            from db import db            # alternative location
            return db
        except ImportError:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: extract sections from a docx file path
# ─────────────────────────────────────────────────────────────────────────────

def _extract_sections_from_docx(docx_path: str):
    """
    Parse a .docx file into a list of {heading, content} dicts.
    Uses python-docx heading styles first, then falls back to heuristics.
    Prints a debug line for every section found.
    """
    try:
        from docx import Document
    except ImportError:
        logger.error("[content_check_router] python-docx not installed")
        return []

    if not os.path.exists(docx_path):
        logger.warning("[content_check_router] docx not found: %s", docx_path)
        return []

    try:
        doc = Document(docx_path)
    except Exception as e:
        logger.error("[content_check_router] Cannot open docx %s: %s", docx_path, e)
        return []

    sections = []
    current_heading = ""
    current_content = []

    def _flush():
        if current_heading and current_content:
            content_str = " ".join(current_content).strip()
            if len(content_str) >= 40:          # skip trivially short sections
                sections.append({
                    "heading": current_heading,
                    "content": content_str,
                })
                print(f"[content_check_router] Section built: '{current_heading}' "
                      f"({len(content_str)} chars)")

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = (para.style.name or "").lower()
        is_heading = (
            "heading" in style_name
            or style_name in ("title", "subtitle")
        )

        # Fallback heuristic if style wasn't applied
        if not is_heading:
            words = text.split()
            if (
                1 <= len(words) <= 10
                and not text.endswith(".")
                and (text.isupper() or text.istitle())
            ):
                is_heading = True

        if is_heading:
            _flush()
            current_heading = text
            current_content = []
        else:
            current_content.append(text)

    _flush()   # flush final section

    print(f"[content_check_router] Total sections extracted: {len(sections)}")
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# Main endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/content-check/{document_id}")
async def run_content_check(
    document_id: int,
    user_id: int = Query(..., description="Authenticated user ID"),
):
    """
    Run the hybrid content checker on a stored document.

    Returns:
        {
            "document_id":    int,
            "total_sections": int,
            "issues":         [ { type, severity, heading, message, ... }, ... ]
        }
    """
    print(f"\n[content_check_router] ▶ POST /content-check/{document_id} "
          f"user_id={user_id}")

    # ── 1. Look up the document path in the database ──────────────────────────
    db = _get_db()
    docx_path = None

    if db is not None:
        try:
            # Most FastAPI/SQLite setups expose something like:
            #   db.get_document(document_id)  →  {"file_path": "...", "user_id": ...}
            # Try the most common patterns found in this codebase:
            row = None
            if hasattr(db, "get_document"):
                row = db.get_document(document_id)
            elif hasattr(db, "fetch_one"):
                row = db.fetch_one(
                    "SELECT file_path FROM documents WHERE id=? AND user_id=?",
                    (document_id, user_id),
                )
            elif hasattr(db, "execute"):
                cur = db.execute(
                    "SELECT file_path FROM documents WHERE id=? AND user_id=?",
                    (document_id, user_id),
                )
                row = cur.fetchone() if cur else None

            if row is None:
                raise HTTPException(status_code=404,
                                    detail=f"Document {document_id} not found for user {user_id}")

            # row may be a dict, sqlite3.Row, or ORM object
            if isinstance(row, dict):
                docx_path = row.get("file_path") or row.get("path") or row.get("upload_path")
            elif hasattr(row, "file_path"):
                docx_path = row.file_path
            elif hasattr(row, "__getitem__"):
                try:
                    docx_path = row["file_path"]
                except (KeyError, IndexError):
                    docx_path = row[0]   # first column

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[content_check_router] DB error: %s", e)
            raise HTTPException(status_code=500, detail=f"Database error: {e}")
    else:
        # ── Fallback: try to find the file in the uploads folder ──────────────
        logger.warning("[content_check_router] No DB helper found — scanning uploads/")
        for root, _dirs, files in os.walk("uploads"):
            for fname in files:
                if str(document_id) in fname and fname.endswith(".docx"):
                    docx_path = os.path.join(root, fname)
                    break
            if docx_path:
                break

    if not docx_path:
        raise HTTPException(status_code=404,
                            detail=f"Could not find file for document {document_id}")

    print(f"[content_check_router] File path: {docx_path}")

    # ── 2. Extract sections ───────────────────────────────────────────────────
    sections = _extract_sections_from_docx(docx_path)

    if not sections:
        print("[content_check_router] No sections extracted — returning empty result")
        return {
            "document_id":    document_id,
            "total_sections": 0,
            "issues":         [],
        }

    # ── 3. Run checker ────────────────────────────────────────────────────────
    content_checker, _ = _get_checkers()

    if content_checker is None:
        # Last-resort: create a fresh instance
        print("[content_check_router] Instantiating ContentChecker (not pre-loaded)")
        try:
            from checker.content_checker import ContentChecker
            content_checker = ContentChecker()
        except Exception as e:
            logger.error("[content_check_router] Cannot load ContentChecker: %s", e)
            raise HTTPException(status_code=500,
                                detail=f"ContentChecker unavailable: {e}")

    print(f"[content_check_router] Running checker on {len(sections)} sections …")
    try:
        issues = content_checker.check(sections)
    except Exception as e:
        logger.error("[content_check_router] Checker error: %s", e)
        raise HTTPException(status_code=500, detail=f"Checker error: {e}")

    print(f"[content_check_router] ✅ Done — {len(issues)} issue(s) found")
    for iss in issues:
        print(f"  [{iss.get('severity','?').upper()}] {iss.get('type')} — "
              f"heading='{iss.get('heading','')}' "
              f"confidence={iss.get('confidence','?')}")

    return {
        "document_id":    document_id,
        "total_sections": len(sections),
        "issues":         issues,
    }