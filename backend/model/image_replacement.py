"""
Image Replacement Models
Tracks image replacements and re-validation history
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ImageReplacementRequest(BaseModel):
    """Request to replace an image and re-validate"""
    document_id: int
    image_index: int  # Which image in the document (0-based)
    # File will be uploaded as multipart/form-data


class ImageReplacementResponse(BaseModel):
    """Response after replacing and re-validating an image"""
    success: bool
    message: str
    image_path: str
    old_image_path: str
    
    # Re-validation results
    is_relevant: bool
    confidence: float
    relevance_score: float
    analysis_details: Optional[dict] = None
    error: Optional[str] = None


class ImageValidationUpdate(BaseModel):
    """Update to image validation status"""
    document_id: int
    image_index: int
    is_relevant: bool
    confidence: float
    validation_timestamp: datetime


class ImageHistory(BaseModel):
    """Track image replacement history"""
    document_id: int
    image_index: int
    original_path: str
    replacement_count: int = 0
    replacements: list = []  # List of {path, date, is_relevant, confidence}
    current_is_relevant: bool
    current_confidence: float
