from fastapi import APIRouter, HTTPException
from typing import List
from database import get_db
from pydantic import BaseModel
import json

router = APIRouter(prefix="/api/templates", tags=["templates"])

class TemplateCreateRequest(BaseModel):
    name: str
    university_id: int
    required_sections: List[dict]
    formatting_rules: dict

class TemplateUpdateRequest(BaseModel):
    name: str
    required_sections: List[dict]
    formatting_rules: dict

@router.get("/user/{user_id}")
async def get_user_templates(user_id: int):
    """Get templates for user's university (User endpoint)"""
    conn = get_db()
    
    # Get user's university
    user = conn.execute(
        "SELECT university_id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    
    if not user or not user["university_id"]:
        conn.close()
        raise HTTPException(status_code=404, detail="User university not found")
    
    # Get all templates for that university
    templates = conn.execute(
        "SELECT * FROM templates WHERE university_id = ? ORDER BY created_at DESC",
        (user["university_id"],)
    ).fetchall()
    conn.close()
    
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "required_sections": json.loads(t["required_sections"]),
            "formatting_rules": json.loads(t["formatting_rules"]),
            "university_id": t["university_id"]
        }
        for t in templates
    ]

@router.get("/university/{university_id}")
async def get_templates(university_id: int):
    """Get all templates for a university"""
    conn = get_db()
    templates = conn.execute(
        "SELECT * FROM templates WHERE university_id = ? ORDER BY created_at DESC",
        (university_id,)
    ).fetchall()
    conn.close()
    
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "required_sections": json.loads(t["required_sections"]),
            "formatting_rules": json.loads(t["formatting_rules"]),
            "university_id": t["university_id"]
        }
        for t in templates
    ]

@router.get("/{template_id}")
async def get_template(template_id: int):
    """Get template details"""
    conn = get_db()
    template = conn.execute(
        "SELECT * FROM templates WHERE id = ?",
        (template_id,)
    ).fetchone()
    conn.close()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": template["id"],
        "name": template["name"],
        "required_sections": json.loads(template["required_sections"]),
        "formatting_rules": json.loads(template["formatting_rules"]),
        "university_id": template["university_id"],
        "created_by": template["created_by"],
        "created_at": template["created_at"]
    }

@router.post("/")
async def create_template(request: TemplateCreateRequest):
    """Create a new template with formatting rules including units and italic styles"""
    conn = get_db()
    
    try:
        # Normalize and validate formatting_rules
        rules = request.formatting_rules
        
        # Ensure spacing unit is set (default to mm if not specified)
        if "spacing_unit" not in rules:
            rules["spacing_unit"] = "mm"
        
        # Validate spacing unit
        if rules.get("spacing_unit") not in ["mm", "cm", "in", "inches"]:
            raise HTTPException(status_code=400, detail="Invalid spacing unit. Use 'mm', 'cm', or 'in'")
        
        # Ensure heading italic options are set
        for level in [1, 2, 3, 4]:
            key = f"heading{level}_italic"
            if key not in rules:
                rules[key] = False
        
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO templates
            (name, university_id, required_sections, formatting_rules, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request.name,
                request.university_id,
                json.dumps(request.required_sections),
                json.dumps(rules),
                request.university_id  # Assuming created_by is the admin/university
            )
        )
        
        conn.commit()
        template_id = cursor.lastrowid
        
        return {
            "id": template_id,
            "name": request.name,
            "required_sections": request.required_sections,
            "formatting_rules": rules,
            "university_id": request.university_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")
    finally:
        conn.close()

@router.put("/{template_id}")
async def update_template(template_id: int, request: TemplateUpdateRequest):
    """Update template with new formatting rules (including units and italic styles)"""
    conn = get_db()
    
    try:
        # Check template exists
        template = conn.execute(
            "SELECT * FROM templates WHERE id = ?",
            (template_id,)
        ).fetchone()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Normalize and validate formatting_rules
        rules = request.formatting_rules
        
        # Ensure spacing unit is set (default to mm if not specified)
        if "spacing_unit" not in rules:
            rules["spacing_unit"] = "mm"
        
        # Validate spacing unit
        if rules.get("spacing_unit") not in ["mm", "cm", "in", "inches"]:
            raise HTTPException(status_code=400, detail="Invalid spacing unit. Use 'mm', 'cm', or 'in'")
        
        # Ensure heading italic options are set
        for level in [1, 2, 3, 4]:
            key = f"heading{level}_italic"
            if key not in rules:
                rules[key] = False
        
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE templates
            SET name = ?, required_sections = ?, formatting_rules = ?
            WHERE id = ?
            """,
            (
                request.name,
                json.dumps(request.required_sections),
                json.dumps(rules),
                template_id
            )
        )
        
        conn.commit()
        
        return {
            "id": template_id,
            "name": request.name,
            "required_sections": request.required_sections,
            "formatting_rules": rules,
            "university_id": template["university_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")
    finally:
        conn.close()

# NOTE:
# Keep spacing and margin values in the same unit the admin selected.
# Conversion is applied only when rendering/exporting documents.
