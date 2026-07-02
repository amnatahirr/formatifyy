"""
fyp_image_formatter_router.py
==============================
Drop into:  backend/routers/fyp_image_formatter_router.py

Then register in backend/main.py:
    from routers.fyp_image_formatter_router import router as formatter_router
    app.include_router(formatter_router, prefix="/api")

Endpoints
---------
POST /api/format-images/{document_id}?user_id=<id>
    Format all images in an existing uploaded document.
    Writes output to uploads/formatted_<document_id>_<timestamp>.docx
    and returns a download URL + full change summary.

GET  /api/format-images/download/{document_id}?user_id=<id>
    Download the most-recently formatted version of the document.
"""

import os
import shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from database import get_db
from services.fyp_image_formatter_service import format_fyp_document

router = APIRouter()

# Formatted outputs are stored here (mirrors your existing "formatted/" folder)
FORMATTED_FOLDER = "formatted"
os.makedirs(FORMATTED_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/format-images/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/format-images/{document_id}")
async def format_document_images(
    document_id: int,
    user_id: int = Query(...),
):
    """
    Apply FYP academic image formatting to all images in the document:
      • Centre-aligned, In-Line-with-Text wrapping
      • Aspect-ratio-preserving resize to fit within page
      • Auto-generated captions (BLIP)  "Figure N: <description>"
      • keepWithNext + keepLines → image + caption never split across pages
      • Consistent spacing before/after every figure
      • Table of Figures appended at the end

    Returns a full summary with per-image details.
    """
    # ── Authorise ─────────────────────────────────────────────────────────────
    conn = get_db()
    doc  = conn.execute(
        "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if not os.path.exists(doc["file_path"]):
        raise HTTPException(status_code=404, detail="Document file not found on server")
    if not doc["file_path"].lower().endswith(".docx"):
        raise HTTPException(
            status_code=400,
            detail="Image formatting is only supported for .docx files."
        )

    # ── Determine the input to format ─────────────────────────────────────────
    # CRITICAL: always read from the working copy if one exists.
    # This means image formatting accumulates on top of any bullet fixes
    # (or other apply-fix changes) that were already applied.
    working_copy = os.path.join(
        "uploads", "working", f"doc_{document_id}_working.docx"
    )
    os.makedirs(os.path.join("uploads", "working"), exist_ok=True)

    if os.path.exists(working_copy):
        input_for_formatter = working_copy
        print(f"[format-images] Using existing working copy: {working_copy}")
    else:
        input_for_formatter = doc["file_path"]
        print(f"[format-images] No working copy yet — starting from original")

    # ── Run formatter — writes result into the working copy ───────────────────
    # We format into a temp path first, then atomically move it to the
    # working copy so a crash never leaves a half-written file.
    ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name   = os.path.splitext(doc["filename"])[0]
    output_name = f"{base_name}_images_formatted_{ts}.docx"
    temp_output = os.path.join(FORMATTED_FOLDER, output_name)

    result = format_fyp_document(input_for_formatter, temp_output)

    if result.get("success") and result.get("total_images", 0) > 0:
        # Promote the formatted file to the shared working copy so that
        # subsequent bullet-apply or other fixes build on top of the image work.
        shutil.copy2(temp_output, working_copy)
        print(f"[format-images] Working copy updated: {working_copy}")
        output_path = temp_output   # keep snapshot in formatted/ for download
    else:
        output_path = temp_output   # no images — output is identical to input

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Formatting failed: {result.get('error', 'unknown error')}"
        )

    if result["total_images"] == 0:
        return {
            "document_id":    document_id,
            "status":         "no_images",
            "message":        "No images found in document — no changes made.",
            "download_url":   None,
            "total_images":   0,
            "captions_added": 0,
            "tof_added":      False,
            "images":         [],
            "manual_items":   [],
        }

    download_url = f"/api/format-images/download/{document_id}?user_id={user_id}&file={output_name}"

    return {
        "document_id":    document_id,
        "status":         "success",
        "message":        (
            f"Formatted {result['total_images']} image(s), "
            f"added {result['captions_added']} caption(s)."
        ),
        "download_url":   download_url,
        "output_filename": output_name,
        "total_images":   result["total_images"],
        "captions_added": result["captions_added"],
        "tof_added":      result["tof_added"],
        "images":         result["images"],
        "manual_items":   result["manual_items"],
        "manual_steps": [
            "Open the formatted file in Word and update each caption text to "
            "describe the actual image content.",
            "Replace the Table of Figures at the end by going to "
            "References → Insert Table of Figures for live page numbers.",
            "For low-resolution images, replace the source with a 300 dpi version.",
            "Update any 'see Figure X' cross-references in the body text using "
            "Word's Insert → Cross-reference.",
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/format-images/download/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/format-images/download/{document_id}")
async def download_formatted_images_doc(
    document_id: int,
    user_id: int  = Query(...),
    file: str     = Query(...),
):
    """
    Download a previously-formatted document by filename.
    The `file` query param is returned by the POST endpoint as `output_filename`.
    """
    conn = get_db()
    doc  = conn.execute(
        "SELECT user_id FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Sanitise — only allow filenames, not paths
    safe_name = os.path.basename(file)
    file_path = os.path.join(FORMATTED_FOLDER, safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Formatted file not found. Re-run formatting.")

    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )