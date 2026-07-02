"""
Image Replacement Router
Handles image replacement and re-validation
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import uuid
import logging
from pathlib import Path
from PIL import Image as PILImage
import io
from docx import Document
import glob

# Import image relevance checker
from services.image_relevance import analyze_image_relevance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["image_replacement"])

UPLOAD_DIR = "uploads"
DOC_DIR = UPLOAD_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------
# Extract images from DOCX
# ---------------------------------------------------------
def extract_docx_images(docx_path):
    """
    Extract images from DOCX and return list of image bytes
    """
    doc = Document(docx_path)
    images = []

    for rel in doc.part.rels.values():
        if rel.reltype == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image":
            image_part = rel.target_part
            images.append(image_part.blob)

    return images


# ---------------------------------------------------------
# Replace image inside DOCX
# ---------------------------------------------------------
def replace_docx_image(docx_path, image_index, new_image_bytes):
    """
    Replace image inside DOCX by index
    """
    doc = Document(docx_path)

    image_counter = 0
    replaced = False

    for rel in doc.part.rels.values():

        if rel.reltype == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image":

            if image_counter == image_index:

                image_part = rel.target_part

                # Replace image blob
                image_part._blob = new_image_bytes

                replaced = True
                logger.info(f"✓ Image replaced in DOCX at index {image_index}")
                break

            image_counter += 1

    if not replaced:
        raise Exception(f"Image index {image_index} not found in DOCX")

    doc.save(docx_path)

    return True


# ---------------------------------------------------------
# API ROUTE
# ---------------------------------------------------------
@router.post("/{document_id}/replace-image")
async def replace_image(
    document_id: int,
    image_index: int = Form(...),
    file: UploadFile = File(...)
):

    try:

        # -------------------------------------------------
        # Validate file
        # -------------------------------------------------
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"

        image_path = os.path.join(UPLOAD_DIR, unique_filename)

        contents = await file.read()

        try:
            img = PILImage.open(io.BytesIO(contents))
            img.verify()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image")

        with open(image_path, "wb") as f:
            f.write(contents)

        logger.info(f"✓ Image saved: {image_path}")

        # -------------------------------------------------
        # Locate DOCX
        # -------------------------------------------------
        possible_files = glob.glob(os.path.join(DOC_DIR, f"*{document_id}*.docx"))

        if not possible_files:
            raise HTTPException(status_code=404, detail="DOCX not found")

        possible_files.sort()
        docx_path = possible_files[-1]

        logger.info(f"Opening DOCX: {docx_path}")

        # -------------------------------------------------
        # Replace image in DOCX
        # -------------------------------------------------
        replace_docx_image(docx_path, image_index, contents)

        logger.info("✓ DOCX saved after replacement")

        # -------------------------------------------------
        # Extract image again from DOCX (IMPORTANT FIX)
        # -------------------------------------------------
        docx_images = extract_docx_images(docx_path)

        if image_index >= len(docx_images):
            raise HTTPException(
                status_code=500,
                detail="Image not found after replacement"
            )

        # Save extracted image temporarily for analysis
        temp_image_path = os.path.join(
            UPLOAD_DIR,
            f"temp_{uuid.uuid4()}.png"
        )

        with open(temp_image_path, "wb") as f:
            f.write(docx_images[image_index])

        logger.info(f"Re-validating DOCX image: {temp_image_path}")

        # -------------------------------------------------
        # Run relevance analysis
        # -------------------------------------------------
        heading = "Section Title"
        before_text = "Previous paragraph"
        after_text = "Following paragraph"

        relevance_analysis = analyze_image_relevance(
            image_path=temp_image_path,
            heading=heading,
            before_text=before_text,
            after_text=after_text,
            image_index=image_index
        )

        is_relevant = relevance_analysis.get("is_relevant", False)
        confidence = relevance_analysis.get("confidence", 0.0)
        relevance_score = relevance_analysis.get("relevance_score", 0.0)

        logger.info(
            f"Image re-validation result: relevant={is_relevant}, confidence={confidence}"
        )

        # -------------------------------------------------
        # Response
        # -------------------------------------------------
        return JSONResponse(
            content={
                "success": True,
                "message": (
                    "Image replaced and validated successfully"
                    if is_relevant
                    else "Image replaced but still not relevant"
                ),
                "image_url": f"/uploads/{unique_filename}",
                "is_relevant": is_relevant,
                "confidence": confidence,
                "relevance_score": relevance_score
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Image replacement failed", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to replace image: {str(e)}"
        )