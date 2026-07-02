from fastapi import APIRouter, HTTPException, Query
from models import UniversityCreate, TemplateCreate, TemplateUpdate, TemplateResponse, RequiredSection, ReferenceFormattingRule
from database import get_db
import json
from datetime import datetime

router = APIRouter(prefix="/api/admin", tags=["admin"])


def check_admin_role(user_id: int) -> bool:
    """Check if user has admin role"""
    conn = get_db()
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user and user["role"] == "admin"


def _migrate_sections(raw: list) -> list:
    """Convert old string-only sections to structured RequiredSection objects"""
    if not raw:
        return []
    migrated = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            # Old plain-string format → upgrade
            migrated.append({"name": item, "order": i + 1, "required": True})
        elif isinstance(item, dict):
            # Ensure all keys exist (safe defaults for older partial dicts)
            migrated.append({
                "name":     item.get("name", ""),
                "order":    item.get("order", i + 1),
                "required": item.get("required", True),
            })
    return migrated


def _sections_to_json(sections) -> str:
    """Serialize required_sections list to JSON string for DB storage."""
    if not sections:
        return json.dumps([])
    result = []
    for s in sections:
        if hasattr(s, "dict"):
            result.append(s.dict())
        elif isinstance(s, dict):
            result.append(s)
        else:
            result.append({"name": str(s), "order": len(result) + 1, "required": True})
    return json.dumps(result)


def _get_default_reference_rules() -> dict:
    
    return {
        "style": "APA",
        "font_name": "Times New Roman",
        "font_size": 12.0,
        "line_spacing": 1.5,
        "hanging_indent": 0.5,
        "space_before": 0.0,
        "space_after": 6.0,
        "bold": False,
        "italic": False,
        "color": "#000000",
        "sort_alphabetically": True,
        "remove_duplicates": True,
        "make_urls_clickable": True,
        "mark_incomplete": True,
        "numbering_style": "numeric"
    }


def _merge_formatting_rules(existing_rules: dict, new_rules: dict) -> dict:
    """
    Merge new formatting rules with existing ones, preserving reference_rules
    if not provided in the new rules.
    """
    # Start with existing rules as base
    merged = existing_rules.copy() if existing_rules else {}
    
    # Update with new rules (overwrites existing fields)
    if new_rules:
        merged.update(new_rules)
    
    # CRITICAL: Ensure reference_rules is always present
    # If new_rules didn't include reference_rules, keep the existing one
    if "reference_rules" not in new_rules and "reference_rules" in existing_rules:
        # Keep existing reference_rules
        merged["reference_rules"] = existing_rules["reference_rules"]
    elif "reference_rules" not in merged or merged["reference_rules"] is None:
        # Initialize with defaults if missing
        merged["reference_rules"] = _get_default_reference_rules()
    
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Universities
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/universities")
async def create_university(university: UniversityCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO universities (name, country) VALUES (?, ?)",
            (university.name, university.country),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "name": university.name, "country": university.country}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.get("/universities")
async def list_universities():
    conn = get_db()
    universities = conn.execute("SELECT * FROM universities").fetchall()
    conn.close()
    return [{"id": u["id"], "name": u["name"], "country": u["country"]} for u in universities]


# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/templates")
async def create_template(
    template: TemplateCreate,
    user_id: int = Query(...),
    university_id: int = Query(...),
):
    """Create a new template (Admin only)"""
    if not check_admin_role(user_id):
        raise HTTPException(status_code=403, detail="Only admins can create templates")

    conn = get_db()
    cursor = conn.cursor()
    try:
        print(f"[admin] Creating template: {template.name} for university: {university_id}")

        # Get formatting rules as dict
        if hasattr(template.formatting_rules, "dict"):
            formatting_rules_dict = template.formatting_rules.dict()
        else:
            formatting_rules_dict = template.formatting_rules
        
        # CRITICAL: Ensure reference_rules exists in new templates
        if "reference_rules" not in formatting_rules_dict or formatting_rules_dict["reference_rules"] is None:
            formatting_rules_dict["reference_rules"] = _get_default_reference_rules()
            print(f"[admin] Initialized reference_rules for new template")
        
        print(f"[admin] Template formatting rules keys: {list(formatting_rules_dict.keys())}")
        print(f"[admin] Has reference_rules: {'reference_rules' in formatting_rules_dict}")

        cursor.execute(
            """
            INSERT INTO templates (university_id, name, required_sections, formatting_rules, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                university_id,
                template.name,
                _sections_to_json(template.required_sections),
                json.dumps(formatting_rules_dict),
                user_id,
            ),
        )
        conn.commit()
        template_id = cursor.lastrowid
        print(f"[admin] Template created with ID: {template_id}")

        return {
            "id": template_id,
            "name": template.name,
            "required_sections": [s.dict() for s in template.required_sections],
            "university_id": university_id,
            "message": "Template created successfully",
        }
    except Exception as e:
        print(f"[admin] Error creating template: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    template: TemplateUpdate,
    user_id: int = Query(...),
):
    """Update a template (Admin only) - Merges formatting rules to preserve reference_rules"""
    if not check_admin_role(user_id):
        raise HTTPException(status_code=403, detail="Only admins can update templates")

    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get current template
        current = cursor.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Template not found")

        # Prepare name
        name = template.name if template.name is not None else current["name"]

        # Prepare required sections
        if template.required_sections is not None:
            required_sections_json = _sections_to_json(template.required_sections)
        else:
            required_sections_json = current["required_sections"]

        # CRITICAL: Merge formatting rules to preserve reference_rules
        # Parse existing formatting_rules
        existing_rules = {}
        if current["formatting_rules"]:
            try:
                existing_rules = json.loads(current["formatting_rules"])
                print(f"[admin] Existing rules keys: {list(existing_rules.keys())}")
            except Exception as e:
                print(f"[admin] Error parsing existing rules: {e}")
                existing_rules = {}
        
        # Prepare new rules from payload
        new_rules = {}
        if template.formatting_rules is not None:
            if hasattr(template.formatting_rules, "dict"):
                new_rules = template.formatting_rules.dict()
            else:
                new_rules = template.formatting_rules
            print(f"[admin] New rules keys: {list(new_rules.keys())}")
        
        # Merge the rules (this preserves reference_rules if not in new_rules)
        merged_rules = _merge_formatting_rules(existing_rules, new_rules)
        
        print(f"[admin] Merged rules keys: {list(merged_rules.keys())}")
        print(f"[admin] Has reference_rules after merge: {'reference_rules' in merged_rules}")
        
        # Convert to JSON
        formatting_rules_json = json.dumps(merged_rules)

        # Update the template
        cursor.execute(
            """
            UPDATE templates
            SET name = ?, required_sections = ?, formatting_rules = ?
            WHERE id = ?
            """,
            (name, required_sections_json, formatting_rules_json, template_id),
        )
        conn.commit()

        # Fetch updated template
        updated = cursor.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()

        sections_raw = json.loads(updated["required_sections"])
        formatting_rules_parsed = json.loads(updated["formatting_rules"])

        print(f"[admin] Template {template_id} updated successfully")
        print(f"[admin] Final reference_rules present: {'reference_rules' in formatting_rules_parsed}")

        return {
            "id": template_id,
            "name": updated["name"],
            "required_sections": _migrate_sections(sections_raw),
            "formatting_rules": formatting_rules_parsed,
            "university_id": updated["university_id"],
            "message": "Template updated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[admin] Error updating template: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, user_id: int):
    if not check_admin_role(user_id):
        raise HTTPException(status_code=403, detail="Only admins can delete templates")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        conn.commit()
        return {"message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.get("/templates/university/{university_id}")
async def get_university_templates(university_id: int):
    conn = get_db()
    templates = conn.execute(
        "SELECT * FROM templates WHERE university_id = ? ORDER BY created_at DESC",
        (university_id,),
    ).fetchall()
    conn.close()

    result = []
    for t in templates:
        formatting_rules = {}
        if t["formatting_rules"]:
            try:
                formatting_rules = json.loads(t["formatting_rules"])
            except:
                formatting_rules = {}
        
        result.append({
            "id": t["id"],
            "name": t["name"],
            "required_sections": _migrate_sections(json.loads(t["required_sections"])),
            "formatting_rules": formatting_rules,
            "university_id": t["university_id"],
            "created_by": t["created_by"],
            "created_at": t["created_at"],
        })
    
    return result


@router.get("/templates/{template_id}")
async def get_template_details(template_id: int):
    conn = get_db()
    template = conn.execute(
        "SELECT * FROM templates WHERE id = ?", (template_id,)
    ).fetchone()
    conn.close()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    sections_raw = json.loads(template["required_sections"])
    formatting_rules = {}
    if template["formatting_rules"]:
        try:
            formatting_rules = json.loads(template["formatting_rules"])
        except:
            formatting_rules = {}

    return {
        "id": template["id"],
        "name": template["name"],
        "required_sections": _migrate_sections(sections_raw),
        "formatting_rules": formatting_rules,
        "university_id": template["university_id"],
        "created_by": template["created_by"],
        "created_at": template["created_at"],
    }


@router.get("/users")
async def list_student_users(user_id: int = Query(...)):
    """List registered student users for admin panel."""
    if not check_admin_role(user_id):
        raise HTTPException(status_code=403, detail="Only admins can view users")

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                u.id,
                u.username,
                u.email,
                u.role,
                u.university_id,
                u.created_at,
                COALESCE(un.name, 'N/A') AS university_name,
                (
                    SELECT COUNT(*)
                    FROM documents d
                    WHERE d.user_id = u.id
                ) AS documents_count
            FROM users u
            LEFT JOIN universities un ON un.id = u.university_id
            WHERE u.role = 'student'
            ORDER BY u.created_at DESC
            """
        ).fetchall()

        return {
            "users": [
                {
                    "id": r["id"],
                    "username": r["username"],
                    "email": r["email"],
                    "role": r["role"],
                    "university_id": r["university_id"],
                    "university_name": r["university_name"],
                    "documents_count": r["documents_count"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ],
            "total": len(rows),
        }
    finally:
        conn.close()


@router.get("/analytics")
async def admin_analytics(user_id: int = Query(...)):
    """Admin analytics summary used by dashboard analytics screen."""
    if not check_admin_role(user_id):
        raise HTTPException(status_code=403, detail="Only admins can view analytics")

    conn = get_db()
    try:
        total_students = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role = 'student'"
        ).fetchone()["c"]
        total_templates = conn.execute(
            "SELECT COUNT(*) AS c FROM templates"
        ).fetchone()["c"]
        total_documents = conn.execute(
            "SELECT COUNT(*) AS c FROM documents"
        ).fetchone()["c"]
        documents_this_month = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM documents
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            """
        ).fetchone()["c"]
        completed_documents = conn.execute(
            "SELECT COUNT(*) AS c FROM documents WHERE status = 'completed'"
        ).fetchone()["c"]
        success_rate = round((completed_documents / total_documents) * 100, 1) if total_documents else 0.0

        daily_rows = conn.execute(
            """
            SELECT
                strftime('%w', created_at) AS weekday_num,
                CASE strftime('%w', created_at)
                    WHEN '0' THEN 'Sun'
                    WHEN '1' THEN 'Mon'
                    WHEN '2' THEN 'Tue'
                    WHEN '3' THEN 'Wed'
                    WHEN '4' THEN 'Thu'
                    WHEN '5' THEN 'Fri'
                    WHEN '6' THEN 'Sat'
                END AS day,
                COUNT(*) AS count
            FROM documents
            WHERE datetime(created_at) >= datetime('now', '-7 days')
            GROUP BY weekday_num
            ORDER BY weekday_num
            """
        ).fetchall()
        documents_last_7_days = [{"day": r["day"], "count": r["count"]} for r in daily_rows]

        template_rows = conn.execute(
            """
            SELECT
                t.id,
                t.name,
                COUNT(d.id) AS uses
            FROM templates t
            LEFT JOIN documents d ON d.template_id = t.id
            GROUP BY t.id
            ORDER BY uses DESC, t.created_at DESC
            LIMIT 5
            """
        ).fetchall()
        top_templates = [{"id": r["id"], "name": r["name"], "uses": r["uses"]} for r in template_rows]

        return {
            "total_students": total_students,
            "total_templates": total_templates,
            "total_documents": total_documents,
            "documents_this_month": documents_this_month,
            "success_rate": success_rate,
            "documents_last_7_days": documents_last_7_days,
            "top_templates": top_templates,
        }
    finally:
        conn.close()