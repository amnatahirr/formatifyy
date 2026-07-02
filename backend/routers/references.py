"""
routers/references.py
"""
from __future__ import annotations
import json, os, shutil, tempfile
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_db
from services.reference_formatter_service import ReferenceFormatterService, ReferenceRules

router = APIRouter(prefix="/api/references", tags=["references"])
_svc = ReferenceFormatterService()

UPLOAD_FOLDER  = "uploads"
WORKING_FOLDER = "uploads/working"
os.makedirs(WORKING_FOLDER, exist_ok=True)

class ReferenceRulesPayload(BaseModel):
    style: str = "APA"
    font_name: str = "Times New Roman"
    font_size: float = 12.0
    line_spacing: float = 1.5
    hanging_indent: float = 0.5
    space_before: float = 0.0
    space_after: float = 6.0
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    sort_alphabetically: bool = True
    remove_duplicates: bool = True
    make_urls_clickable: bool = True
    mark_incomplete: bool = True
    numbering_style: str = "numeric"

def _working_copy_path(document_id: int) -> str:
    return os.path.join(WORKING_FOLDER, f"doc_{document_id}_working.docx")

def _get_effective_path(document_id: int, original_path: str) -> str:
    wc = _working_copy_path(document_id)
    return wc if os.path.exists(wc) else original_path

def _get_document(document_id: int) -> dict:
    conn = get_db()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    conn.close()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(doc)

def _get_reference_rules(document_id: int) -> dict:
    """
    Fetch reference_rules from the document's template.
    Returns {} (uses service defaults) if no template or no rules configured.
    This makes the endpoint work even without admin configuration.
    """
    conn = get_db()
    doc = conn.execute("SELECT template_id FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not doc or not doc["template_id"]:
        conn.close()
        print(f"[references] doc {document_id} has no template → using default APA rules")
        return {}
    template = conn.execute(
        "SELECT formatting_rules FROM templates WHERE id = ?", (doc["template_id"],)
    ).fetchone()
    conn.close()
    if not template:
        return {}
    try:
        return json.loads(template["formatting_rules"]).get("reference_rules") or {}
    except Exception:
        return {}

@router.post("/format/{document_id}")
async def format_references(document_id: int, user_id: int = Query(...)):
    doc = _get_document(document_id)
    original_path = doc["file_path"]
    if not os.path.exists(original_path):
        raise HTTPException(status_code=404, detail=f"File not found: {original_path}")
    working_path = _working_copy_path(document_id)
    if not os.path.exists(working_path):
        shutil.copy2(original_path, working_path)
    rules = ReferenceRules.from_dict(_get_reference_rules(document_id))
    result = _svc.format_references(working_path, rules)
    return {
        "document_id": document_id, "success": result.success,
        "message": result.message,
        "references_found": result.references_found,
        "duplicates_removed": result.duplicates_removed,
        "incomplete_count": result.incomplete_count,
        "urls_linked": result.urls_linked,
        "working_copy": working_path,
    }

@router.get("/preview/{document_id}")
async def preview_references(document_id: int):
    doc = _get_document(document_id)
    original_path = doc["file_path"]
    if not os.path.exists(original_path):
        raise HTTPException(status_code=404, detail=f"File not found: {original_path}")
    effective_path = _get_effective_path(document_id, original_path)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    os.close(tmp_fd)
    try:
        shutil.copy2(effective_path, tmp_path)
        rules = ReferenceRules.from_dict(_get_reference_rules(document_id))
        result = _svc.format_references(tmp_path, rules)
    finally:
        try: os.remove(tmp_path)
        except OSError: pass
    return {
        "document_id": document_id, "success": result.success,
        "message": result.message,
        "references_found": result.references_found,
        "duplicates_removed": result.duplicates_removed,
        "incomplete_count": result.incomplete_count,
        "urls_linked": result.urls_linked,
        "preview": result.details,
    }

@router.get("/rules/{template_id}")
async def get_reference_rules(template_id: int):
    conn = get_db()
    template = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    conn.close()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        formatting_rules = json.loads(template["formatting_rules"])
    except Exception:
        formatting_rules = {}
    ref_rules = formatting_rules.get("reference_rules") or {}
    defaults = ReferenceRulesPayload().dict()
    defaults.update(ref_rules)
    return {"template_id": template_id, "reference_rules": defaults}

@router.put("/rules/{template_id}")
async def update_reference_rules(
    template_id: int, 
    payload: ReferenceRulesPayload, 
    user_id: int = Query(...)
):
    print(f"\n=== UPDATING REFERENCE RULES ===")
    print(f"Template ID: {template_id}")
    print(f"User ID: {user_id}")
    print(f"Payload received: {payload.dict()}")
    
    conn = get_db()
    
    # Check admin permissions
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user or user["role"] != "admin":
        conn.close()
        raise HTTPException(status_code=403, detail="Only admins can update template rules")
    
    # Get template
    template = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    if not template:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Parse existing formatting_rules
    try:
        formatting_rules = json.loads(template["formatting_rules"]) if template["formatting_rules"] else {}
        print(f"Existing formatting_rules keys: {list(formatting_rules.keys())}")
    except Exception as e:
        print(f"Error parsing formatting_rules: {e}")
        formatting_rules = {}
    
    # Update only the reference_rules part
    formatting_rules["reference_rules"] = payload.dict()
    print(f"Updated reference_rules: {formatting_rules['reference_rules']}")
    
    # Save back to the formatting_rules column
    conn.execute(
        "UPDATE templates SET formatting_rules = ? WHERE id = ?",
        (json.dumps(formatting_rules), template_id)
    )
    conn.commit()
    
    # Verify the save
    verify = conn.execute("SELECT formatting_rules FROM templates WHERE id = ?", (template_id,)).fetchone()
    print(f"Verification after save: {json.loads(verify['formatting_rules'])['reference_rules']}")
    
    conn.close()
    
    print(f"=== UPDATE COMPLETE ===\n")
    
    return {
        "template_id": template_id, 
        "message": "Reference rules updated successfully",
        "reference_rules": payload.dict()
    }