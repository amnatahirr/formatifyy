from fastapi import APIRouter, UploadFile, File, HTTPException, Query
import shutil
import os
import uuid

from database import get_db
from services.image_relevance import analyze_image_relevance, extract_images_with_full_context
from services.image_detector import image_detector
from services.document_parser import parser

router = APIRouter()


# =====================================================
# SHARED HELPER
# =====================================================

def _save_upload(file: UploadFile) -> str:
    """
    Save an uploaded file to the uploads/ folder with a unique name.
    Returns the saved file path.
    """
    os.makedirs("uploads", exist_ok=True)
    unique_name = f"{uuid.uuid4()}_{file.filename}"
    path = os.path.join("uploads", unique_name)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return path


def _cleanup(paths: list):
    """Delete temporary files after analysis to avoid disk buildup."""
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


# =====================================================
# ENDPOINT 1 — IMAGE RELEVANCE CHECK
# =====================================================

@router.post("/check-image-relevance")
async def check_relevance(file: UploadFile = File(...)):
    """
    Accept a .docx file, extract all images with their surrounding context,
    and run relevancy analysis on each image.

    Returns per-image relevance scores and an overall threshold.
    """
    docx_path = _save_upload(file)
    saved_image_paths = []

    try:
        # Extract images with context (saves PNGs to uploads/, returns list of dicts)
        image_contexts = parser.extract_images_with_context(docx_path)

        if not image_contexts:
            return {
                "total_images": 0,
                "results": [],
                "message": "No images found in the document."
            }

        results = []
        for ctx in image_contexts:
            saved_image_paths.append(ctx["image_path"])

            # analyze_image_relevance() takes a single image path + context fields
            result = analyze_image_relevance(
                image_path=ctx["image_path"],
                heading=ctx["heading"],
                before_text=ctx["before_text"],
                after_text=ctx["after_text"],
            )
            results.append({
                "image_path":        ctx["image_path"],
                "heading":           ctx["heading"],
                "relevant":          result["relevant"],
                "final_score":       result["final_score"],
                "threshold":         result["threshold"],
                "caption":           result["caption"],
                "matching_keywords": result["matching_keywords"],
                # Score breakdown for debugging / display
                "scores": {
                    "clip":          result["clip_score"],
                    "sbert":         result["combined_sbert"],
                    "cross_encoder": result["cross_score"],
                    "keyword":       result["keyword_overlap"],
                },
            })

        irrelevant_count = sum(1 for r in results if not r["relevant"])

        return {
            "total_images":     len(results),
            "irrelevant_count": irrelevant_count,
            "results":          results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relevance check failed: {str(e)}")

    finally:
        # Clean up the docx and all extracted image files
        _cleanup([docx_path] + saved_image_paths)


# =====================================================
# ENDPOINT 2 — IMAGE ETHICS CHECK  (NEW)
# =====================================================

@router.post("/check-image-ethics")
async def check_ethics(file: UploadFile = File(...)):
    """
    Accept a .docx file, extract all images, and run ethics analysis
    on each image using the BLIP caption → taxonomy classifier pipeline.

    Returns all images with their ethics verdict, and separately lists
    only the flagged (unethical) images for the analysis screen to display.
    """
    docx_path = _save_upload(file)
    saved_image_paths = []

    try:
        # Extract images with context (saves PNGs to uploads/, returns list of dicts)
        image_contexts = parser.extract_images_with_context(docx_path)

        if not image_contexts:
            return {
                "total_images":   0,
                "flagged_count":  0,
                "flagged_images": [],
                "all_results":    [],
                "message":        "No images found in the document."
            }

        saved_image_paths = [ctx["image_path"] for ctx in image_contexts]

        # Run ethics analysis on all images (document_id=0 for router-level calls)
        all_results = image_detector.analyze_document_images(
            document_id=0,
            image_contexts=image_contexts,
        )

        # Separate flagged images — these are shown as errors on the analysis screen
        flagged = [r for r in all_results if not r["is_safe"]]

        return {
            "total_images":   len(all_results),
            "flagged_count":  len(flagged),
            "flagged_images": flagged,   # Only these shown as errors on analysis screen
            "all_results":    all_results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ethics check failed: {str(e)}")

    finally:
        # Clean up the docx and all extracted image files
        _cleanup([docx_path] + saved_image_paths)


# =====================================================
# ENDPOINT 3 — COMBINED CHECK  (relevance + ethics in one call)
# =====================================================

@router.post("/check-images")
async def check_images(file: UploadFile = File(...)):
    """
    Run BOTH relevance and ethics checks in a single request.
    This is the recommended endpoint for your analysis screen —
    one upload gives you all image errors at once.

    Returns:
    - flagged_ethics   : images that are unethical (must fix before formatting)
    - flagged_relevance: images that are irrelevant to their surrounding context
    - all_results      : full per-image breakdown
    """
    docx_path = _save_upload(file)
    saved_image_paths = []

    try:
        image_contexts = parser.extract_images_with_context(docx_path)

        if not image_contexts:
            return {
                "total_images":      0,
                "flagged_ethics":    [],
                "flagged_relevance": [],
                "all_results":       [],
                "message":           "No images found in the document."
            }

        saved_image_paths = [ctx["image_path"] for ctx in image_contexts]
        all_results = []

        for ctx in image_contexts:
            # ── Ethics ──────────────────────────────────────────────────────
            ethics_result = image_detector.analyze_image(ctx["image_path"])

            # ── Relevance ────────────────────────────────────────────────────
            relevance_result = analyze_image_relevance(
                image_path=ctx["image_path"],
                heading=ctx["heading"],
                before_text=ctx["before_text"],
                after_text=ctx["after_text"],
            )

            all_results.append({
                "image_path": ctx["image_path"],
                "heading":    ctx["heading"],

                # Ethics fields
                "is_safe":          ethics_result["is_safe"],
                "ethics_category":  ethics_result["category"],
                "ethics_warnings":  ethics_result["warnings"],
                "ethics_caption":   ethics_result["caption"],
                "safe_override":    ethics_result["safe_override"],

                # Relevance fields
                "relevant":          relevance_result["relevant"],
                "relevance_score":   relevance_result["final_score"],
                "relevance_caption": relevance_result["caption"],
                "matching_keywords": relevance_result["matching_keywords"],
            })

        flagged_ethics    = [r for r in all_results if not r["is_safe"]]
        flagged_relevance = [r for r in all_results if not r["relevant"]]

        return {
            "total_images":      len(all_results),
            "flagged_ethics":    flagged_ethics,
            "flagged_relevance": flagged_relevance,
            "all_results":       all_results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image check failed: {str(e)}")

    finally:
        _cleanup([docx_path] + saved_image_paths)


# =====================================================
# ENDPOINT 4 — CHECK IMAGES BY DOCUMENT ID
# Flutter calls this with just document_id — no file upload needed
# Backend fetches the file path from DB itself
# =====================================================

@router.post("/check-images-by-id")
async def check_images_by_id(
    document_id: int = Query(...),
    user_id: int = Query(...),
):
    """
    Run combined ethics + relevance check using document_id.
    Flutter sends document_id — backend reads the file from DB path.
    No file upload needed from client.
    """
    saved_image_paths = []

    try:
        # Get file path from database
        conn = get_db()
        doc = conn.execute(
            "SELECT file_path, user_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()
        conn.close()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        docx_path = doc["file_path"]

        if not os.path.exists(docx_path):
            raise HTTPException(status_code=404, detail="Document file not found on server")

        # Extract images with context
        image_contexts = parser.extract_images_with_context(docx_path)

        if not image_contexts:
            return {
                "total_images":      0,
                "flagged_ethics":    [],
                "flagged_relevance": [],
                "all_results":       [],
                "message":           "No images found in the document."
            }

        saved_image_paths = [ctx["image_path"] for ctx in image_contexts]
        all_results = []

        for ctx in image_contexts:
            # Ethics check
            ethics_result = image_detector.analyze_image(ctx["image_path"])

            # Relevance check
            relevance_result = analyze_image_relevance(
                image_path=ctx["image_path"],
                heading=ctx["heading"],
                before_text=ctx["before_text"],
                after_text=ctx["after_text"],
            )

            all_results.append({
                "image_path":        ctx["image_path"],
                "heading":           ctx["heading"],
                "is_safe":           ethics_result["is_safe"],
                "ethics_category":   ethics_result["category"],
                "ethics_warnings":   ethics_result["warnings"],
                "ethics_caption":    ethics_result["caption"],
                "safe_override":     ethics_result["safe_override"],
                "relevant":          relevance_result["relevant"],
                "relevance_score":   relevance_result["final_score"],
                "relevance_caption": relevance_result["caption"],
                "matching_keywords": relevance_result["matching_keywords"],
            })

        flagged_ethics    = [r for r in all_results if not r["is_safe"]]
        flagged_relevance = [r for r in all_results if not r["relevant"]]

        return {
            "total_images":      len(all_results),
            "flagged_ethics":    flagged_ethics,
            "flagged_relevance": flagged_relevance,
            "all_results":       all_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image check failed: {str(e)}")
    