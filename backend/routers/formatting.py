from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import uuid
import json
import ast

from database import get_db
from services.section_detector import detector
from services.formatter import formatter
from formatter.docx_formatter import format_docx
from routers.format_document import build_formatted_elements_for_file, export_elements_to_docx

router = APIRouter(prefix="/api/formatting", tags=["formatting"])

# Ensure upload/output directories exist
UPLOAD_DIR = "uploads/"
OUTPUT_DIR = "outputs/"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def _safe_parse_json_field(raw_value, default):
    """Safely parse stored JSON/list-like text without using eval()."""
    if raw_value is None:
        return default
    if isinstance(raw_value, (list, dict)):
        return raw_value
    if not isinstance(raw_value, str):
        return default

    raw_value = raw_value.strip()
    if not raw_value:
        return default

    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        try:
            parsed = ast.literal_eval(raw_value)
            return parsed if isinstance(parsed, type(default)) else default
        except (ValueError, SyntaxError):
            return default


# ---------- Endpoint 1: Get formatting suggestions ----------
@router.get("/suggestions/{document_id}")
async def get_formatting_suggestions(document_id: int):
    """Get formatting suggestions for a document"""
    conn = get_db()
    
    doc = conn.execute(
        "SELECT missing_sections, template_id FROM documents WHERE id = ?",
        (document_id,)
    ).fetchone()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    missing_sections = _safe_parse_json_field(doc["missing_sections"], [])
    suggestions = detector.generate_suggestions(missing_sections)
    
    conn.close()
    
    return {
        "document_id": document_id,
        "missing_sections": missing_sections,
        "suggestions": suggestions
    }


# ---------- Endpoint 2: Apply formatting based on template ----------
@router.post("/apply/{document_id}")
async def apply_formatting(document_id: int):
    """Apply formatting rules to a document"""
    conn = get_db()
    
    doc = conn.execute(
        "SELECT * FROM documents WHERE id = ?",
        (document_id,)
    ).fetchone()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get template formatting rules
    template = conn.execute(
        "SELECT formatting_rules FROM templates WHERE id = ?",
        (doc["template_id"],)
    ).fetchone()
    
    formatting_rules = json.loads(template["formatting_rules"]) if template else formatter.default_rules
    
    # In production, parse the actual document and apply rules
    # For now, return mock formatted content
    formatted_content = {
        "document_id": document_id,
        "status": "formatted",
        "preview": {
            "title": "Your Document",
            "formatted_sections": _safe_parse_json_field(doc["detected_sections"], [])
        }
    }
    
    # Update document status
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE documents SET status = ? WHERE id = ?",
        ("formatted", document_id)
    )
    conn.commit()
    conn.close()
    
    return formatted_content


# ---------- Endpoint 3: Upload and format a .docx file with template ----------
@router.post("/format-document/")
async def format_document(file: UploadFile = File(...), template_id: int = None):
    """
    Upload a .docx file and format it using template rules.
    
    Args:
        file: DOCX file to format
        template_id: Optional template ID to use for formatting
    """
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # Get template rules if provided
    template_rules = None
    if template_id:
        conn = get_db()
        template = conn.execute(
            "SELECT formatting_rules FROM templates WHERE id = ?",
            (template_id,)
        ).fetchone()
        conn.close()
        
        if template:
            template_rules = json.loads(template["formatting_rules"])
    
    # Generate unique file paths
    file_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}.docx")
    output_path = os.path.join(OUTPUT_DIR, f"{file_id}_formatted.docx")
    
    # Save uploaded file
    with open(input_path, "wb") as f:
        f.write(await file.read())
    
    # Bridge legacy endpoint to the primary smart formatting pipeline
    elements = build_formatted_elements_for_file(
        input_path,
        template_id=template_id,
        template_rules=template_rules,
    )
    export_elements_to_docx(elements, output_path)
    
    # Return formatted file
    return FileResponse(output_path, filename=f"{file.filename}_formatted.docx")
