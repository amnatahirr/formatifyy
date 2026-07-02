"""
Bullet Detection Router
API endpoints for detecting and managing bullet formatting
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import uuid
import json

from services.bullet_detection_service import BulletDetectionService
from services.bullet_formatter_service import BulletFormatterService

router = APIRouter(prefix="/api/bullets", tags=["bullet_detection"])

# Initialize services
detection_service = BulletDetectionService()
formatter_service = BulletFormatterService()

UPLOAD_DIR = "uploads/"
OUTPUT_DIR = "outputs/"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class BulletDetectionRequest(BaseModel):
    """Request to detect bullets in document blocks"""
    blocks: List[Dict[str, Any]]
    auto_group: bool = True


class BulletDetectionResponse(BaseModel):
    """Response with detected bullets"""
    detected_bullets: List[Dict[str, Any]]
    bullet_groups: List[List[Dict[str, Any]]] = []
    total_detected: int
    summary: Dict[str, Any]


@router.post(
    "/detect",
    summary="Detect bullet points in document blocks",
    response_model=BulletDetectionResponse
)
async def detect_bullets(request: BulletDetectionRequest) -> BulletDetectionResponse:
    """
    Analyze document blocks and detect content that should be formatted as bullets.
    
    Args:
        request: Contains document blocks to analyze
        
    Returns:
        Detected bullets with confidence scores and grouping info
    """
    try:
        # Detect bullets
        detected = detection_service.detect_bullets_in_blocks(request.blocks)
        
        # Convert to dicts for JSON response
        detected_dicts = [
            {
                "text": b.text,
                "index": b.index,
                "confidence": b.confidence,
                "reason": b.reason
            }
            for b in detected
        ]
        
        # Group consecutive bullets if requested
        bullet_groups = []
        if request.auto_group:
            groups = detection_service.group_consecutive_bullets(detected)
            bullet_groups = [
                [
                    {
                        "text": b.text,
                        "index": b.index,
                        "confidence": b.confidence,
                        "reason": b.reason
                    }
                    for b in group
                ]
                for group in groups
            ]
        
        # Create summary
        summary = {
            "total_blocks": len(request.blocks),
            "high_confidence": len([d for d in detected if d.confidence > 0.8]),
            "medium_confidence": len([d for d in detected if 0.6 < d.confidence <= 0.8]),
            "low_confidence": len([d for d in detected if d.confidence <= 0.6]),
            "total_groups": len(bullet_groups)
        }
        
        return BulletDetectionResponse(
            detected_bullets=detected_dicts,
            bullet_groups=bullet_groups,
            total_detected=len(detected_dicts),
            summary=summary
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bullet detection failed: {str(e)}")


@router.post(
    "/apply",
    summary="Apply bullet formatting to document",
    response_model=Dict[str, Any]
)
async def apply_bullet_formatting(
    file: UploadFile = File(...),
    formatting_rules: Optional[str] = Query(None),
    auto_detect: bool = Query(True)
) -> Dict[str, Any]:
    """
    Upload a DOCX file and apply bullet formatting based on detected content or rules.
    
    Args:
        file: DOCX file to format
        formatting_rules: JSON string with template formatting rules
        auto_detect: Whether to auto-detect bullets
        
    Returns:
        Path to formatted file and summary
    """
    try:
        if not file.filename.endswith(".docx"):
            raise HTTPException(status_code=400, detail="Only .docx files supported")
        
        # Parse formatting rules
        rules = {}
        if formatting_rules:
            try:
                rules = json.loads(formatting_rules)
            except json.JSONDecodeError:
                pass
        
        # Generate file paths
        file_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_DIR, f"{file_id}_input.docx")
        output_path = os.path.join(OUTPUT_DIR, f"{file_id}_bullets.docx")
        
        # Save uploaded file
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)
        
        # Apply formatting
        success = formatter_service.apply_bullet_formatting(
            input_path,
            output_path,
            formatting_rules=rules
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Formatting failed")
        
        return {
            "status": "success",
            "message": "Bullet formatting applied",
            "output_file": output_path,
            "file_id": file_id,
            "rules_applied": rules
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying bullets: {str(e)}")


@router.post(
    "/apply-to-file/{file_id}",
    summary="Apply bullet formatting to uploaded document"
)
async def apply_bullets_to_file(
    file_id: str,
    formatting_rules: Optional[str] = Query(None)
) -> FileResponse:
    """
    Apply bullet formatting to an already-uploaded document.
    
    Args:
        file_id: ID of uploaded file
        formatting_rules: JSON string with template rules
        
    Returns:
        Formatted DOCX file
    """
    try:
        input_path = os.path.join(UPLOAD_DIR, f"{file_id}.docx")
        
        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Parse rules
        rules = {}
        if formatting_rules:
            try:
                rules = json.loads(formatting_rules)
            except json.JSONDecodeError:
                pass
        
        # Format with bullets
        output_path = os.path.join(OUTPUT_DIR, f"{file_id}_bullets.docx")
        success = formatter_service.apply_bullet_formatting(
            input_path,
            output_path,
            formatting_rules=rules
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Formatting failed")
        
        return FileResponse(
            output_path,
            filename=f"formatted_bullets.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
