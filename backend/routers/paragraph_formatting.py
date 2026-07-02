"""
API endpoints for paragraph-level formatting control
Allows users to customize paragraph properties like spacing, alignment, and font
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import uuid
import json
from pydantic import BaseModel
from typing import Optional

from formatter.paragraph_formatter import paragraph_formatter
from docx import Document

router = APIRouter(prefix="/api/paragraph", tags=["paragraph_formatting"])

# Ensure upload/output directories exist
UPLOAD_DIR = "uploads/"
OUTPUT_DIR = "outputs/"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class ParagraphSettings(BaseModel):
    """Settings for paragraph formatting"""
    font_name: str = "Times New Roman"
    font_size: int = 11
    space_before: int = 0
    space_after: int = 6
    line_spacing: float = 1.0
    alignment: str = "justify"  # justify, left, center, right
    text_bold: bool = False
    text_italic: bool = False


class DocumentFormattingConfig(BaseModel):
    """Configuration for document-level formatting"""
    left_margin: float = 1.0
    right_margin: float = 1.0
    top_margin: float = 1.0
    bottom_margin: float = 1.0
    font_name: str = "Times New Roman"
    font_size: int = 11
    line_spacing: float = 1.0
    paragraph_space_after: int = 6


class AdvancedMarginConfig(BaseModel):
    """Advanced margin configuration with gutter support"""
    top_margin: float = 1.0
    bottom_margin: float = 1.0
    left_margin: float = 1.0
    right_margin: float = 1.0
    gutter: float = 0.2
    gutter_position: str = "left"  # "left" or "right"
    font_name: str = "Times New Roman"
    font_size: int = 11
    line_spacing: float = 1.0
    paragraph_space_before: int = 0
    paragraph_space_after: int = 6


@router.post("/apply-paragraph-settings/")
async def apply_paragraph_settings(file: UploadFile = File(...), 
                                  settings: ParagraphSettings = ParagraphSettings()):
    """
    Apply paragraph formatting settings to all paragraphs in a document
    """
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # Generate unique file paths
    file_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}.docx")
    output_path = os.path.join(OUTPUT_DIR, f"{file_id}_formatted.docx")
    
    # Save uploaded file
    with open(input_path, "wb") as f:
        f.write(await file.read())
    
    # Load document
    doc = Document(input_path)
    
    # Apply settings to all paragraphs
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():  # Only format non-empty paragraphs
            for run in paragraph.runs:
                paragraph_formatter.set_font_properties(
                    run,
                    font_size=settings.font_size,
                    bold=settings.text_bold,
                    italic=settings.text_italic,
                    font_name=settings.font_name
                )
            
            # Apply paragraph spacing
            paragraph_formatter.set_paragraph_spacing(
                paragraph,
                space_before=settings.space_before,
                space_after=settings.space_after,
                line_spacing=settings.line_spacing
            )
    
    # Save formatted document
    doc.save(output_path)
    
    return FileResponse(output_path, filename=f"{file.filename}_formatted.docx")


@router.post("/format-document-advanced/")
async def format_document_advanced(file: UploadFile = File(...),
                                   config: DocumentFormattingConfig = DocumentFormattingConfig()):
    """
    Apply advanced document formatting including margins, spacing, and font settings
    """
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # Generate unique file paths
    file_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}.docx")
    output_path = os.path.join(OUTPUT_DIR, f"{file_id}_formatted.docx")
    
    # Save uploaded file
    with open(input_path, "wb") as f:
        f.write(await file.read())
    
    # Load document
    doc = Document(input_path)
    
    # Set document margins
    for section in doc.sections:
        from docx.shared import Inches
        section.top_margin = Inches(config.top_margin)
        section.bottom_margin = Inches(config.bottom_margin)
        section.left_margin = Inches(config.left_margin)
        section.right_margin = Inches(config.right_margin)
    
    # Apply formatting to all paragraphs
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            for run in paragraph.runs:
                paragraph_formatter.set_font_properties(
                    run,
                    font_size=config.font_size,
                    font_name=config.font_name
                )
            
            paragraph_formatter.set_paragraph_spacing(
                paragraph,
                space_before=0,
                space_after=config.paragraph_space_after,
                line_spacing=config.line_spacing
            )
    
    # Save formatted document
    doc.save(output_path)
    
    return FileResponse(output_path, filename=f"{file.filename}_formatted.docx")


@router.post("/apply-margins-advanced/")
async def apply_margins_advanced(file: UploadFile = File(...),
                                 config: AdvancedMarginConfig = AdvancedMarginConfig()):
    """
    Apply advanced margin settings to document according to Figure 2 specifications.
    
    Features:
    - Individual control for top, bottom, left, right margins
    - Gutter support for binding margins
    - Automatic paragraph formatting
    - Default values match FYP requirements (1" margins, 0.2" gutter)
    """
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # Generate unique file paths
    file_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}.docx")
    output_path = os.path.join(OUTPUT_DIR, f"{file_id}_margins.docx")
    
    # Save uploaded file
    with open(input_path, "wb") as f:
        f.write(await file.read())
    
    # Load document
    doc = Document(input_path)
    
    # Apply advanced margins with gutter
    paragraph_formatter.set_document_margins_advanced(
        doc,
        top_margin=config.top_margin,
        bottom_margin=config.bottom_margin,
        left_margin=config.left_margin,
        right_margin=config.right_margin,
        gutter=config.gutter,
        gutter_position=config.gutter_position
    )
    
    # Apply paragraph formatting
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            for run in paragraph.runs:
                paragraph_formatter.set_font_properties(
                    run,
                    font_size=config.font_size,
                    font_name=config.font_name
                )
            
            paragraph_formatter.set_paragraph_spacing(
                paragraph,
                space_before=config.paragraph_space_before,
                space_after=config.paragraph_space_after,
                line_spacing=config.line_spacing
            )
    
    # Save formatted document
    doc.save(output_path)
    
    return {
        "status": "success",
        "message": "Margins applied successfully according to Figure 2 specifications",
        "applied_margins": {
            "top_inch": config.top_margin,
            "bottom_inch": config.bottom_margin,
            "left_inch": config.left_margin,
            "right_inch": config.right_margin,
            "gutter_inch": config.gutter,
            "gutter_position": config.gutter_position
        },
        "file_id": file_id,
        "download_url": f"/download/{file_id}_margins.docx"
    }


@router.get("/spec-info/")
async def get_formatting_specifications():
    """
    Get document formatting specifications (A4, margins, fonts, etc.)
    """
    return {
        "paper_size": "A4",
        "paper_dimensions": {
            "width_mm": 210,
            "height_mm": 297,
            "width_inches": 8.27,
            "height_inches": 11.7
        },
        "default_margins": {
            "top_inches": 1.0,
            "bottom_inches": 1.0,
            "left_inches": 1.0,
            "right_inches": 1.0
        },
        "font_specifications": {
            "family": "Times New Roman",
            "size_body": 11,
            "size_heading1": 16,
            "size_heading2": 14,
            "size_heading3": 13,
            "size_bullet": 12
        },
        "paragraph_spacing": {
            "line_spacing": 1.0,
            "space_before_pt": 0,
            "space_after_pt": 6
        },
        "text_alignment": "justified"
    }


@router.get("/margin-specifications/")
async def get_margin_specifications():
    """
    Get default margin specifications according to Figure 2.
    
    Returns A4 paper margins:
    - Top: 1 inch
    - Bottom: 1 inch
    - Left: 1 inch
    - Right: 1 inch
    - Gutter: 0.2 inches (left)
    - Orientation: Portrait
    """
    return {
        "standard_margins": {
            "top_inch": 1.0,
            "bottom_inch": 1.0,
            "left_inch": 1.0,
            "right_inch": 1.0
        },
        "gutter": {
            "width_inch": 0.2,
            "position": "left"
        },
        "paper": {
            "size": "A4",
            "orientation": "Portrait",
            "width_inch": 8.27,
            "height_inch": 11.7
        },
        "multiple_pages": "Normal",
        "note": "Specifications according to Figure 2 - Template page margins"
    }
