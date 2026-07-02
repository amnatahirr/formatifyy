"""
templates.py — Predefined and dynamic formatting templates for Formatify.

Integrates with sqlite database (database.py) to load, store, delete,
and retrieve templates. Converts JSON template specifications into the
exact markdown rules prompt injected into LLM checkers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from database import get_db, init_db


def generate_markdown_rules(name: str, required_sections: List[str], rules: Dict[str, Any]) -> str:
    """
    Dynamically translate database-stored templates (JSON config) into a single
    markdown rules prompt. Matches what LLMs and python-docx expect.
    """
    sections_text = "\n".join(
        f"{idx + 1}. {sec}" for idx, sec in enumerate(required_sections)
    )

    def format_heading(prefix: str) -> str:
        font = rules.get(f"{prefix}_font", "Times New Roman")
        size = rules.get(f"{prefix}_size", 12)
        bold = "Bold" if rules.get(f"{prefix}_bold", True) else "Regular"
        italic = "Italic" if rules.get(f"{prefix}_italic", False) else "Non-Italic"
        line_spacing = rules.get(f"{prefix}_line_spacing", 1.5)
        space_before = rules.get(f"{prefix}_space_before", 12.0)
        space_after = rules.get(f"{prefix}_space_after", 6.0)

        return (
            f"{font}, {size}pt, {bold}, {italic}, "
            f"Line Spacing {line_spacing}, "
            f"Space Before {space_before}pt, Space After {space_after}pt"
        )

    h1_style = format_heading("heading1")
    h2_style = format_heading("heading2")
    h3_style = format_heading("heading3")

    body_font = rules.get("body_font", "Times New Roman")
    body_size = rules.get("body_size", 12)
    body_line_spacing = rules.get("body_line_spacing", 1.5)
    body_space_before = rules.get("body_space_before", 0.0)
    body_space_after = rules.get("body_space_after", 0.0)
    first_line_indent = rules.get("first_line_indent", 0.5)

    margin_top = rules.get("margin_top", 1.0)
    margin_bottom = rules.get("margin_bottom", 1.0)
    margin_left = rules.get("margin_left", 1.0)
    margin_right = rules.get("margin_right", 1.0)
    page_size = rules.get("page_size", "A4")

    return f"""# {name} Template

## Required Sections (in order)
{sections_text}

## Heading Styles
- **Heading 1**: {h1_style}
- **Heading 2**: {h2_style}
- **Heading 3**: {h3_style}

## Body Text
- Font: {body_font}, {body_size}pt
- Line Spacing: {body_line_spacing}
- Space Before: {body_space_before}pt
- Space After: {body_space_after}pt
- First Line Indent: {first_line_indent} inches

## Page Layout
- Margins: Top {margin_top} inches, Bottom {margin_bottom} inches, Left {margin_left} inches, Right {margin_right} inches
- Page Size: {page_size}
"""


def get_all_templates() -> List[Dict[str, Any]]:
    """Return all templates for general listing."""
    init_db()  # Ensure tables seeded
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM templates ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        req_sections = json.loads(r["required_sections"] or "[]")
        rules = json.loads(r["formatting_rules"] or "{}")
        markdown_rules = generate_markdown_rules(r["name"], req_sections, rules)
        result.append({
            "id": r["id"],
            "name": r["name"],
            "description": r["description"] or "",
            "required_sections": req_sections,
            "formatting_rules": rules,
            "markdown_rules": markdown_rules,
            "university_id": r["university_id"],
            "created_by": r["created_by"],
            "created_at": str(r["created_at"])
        })
    return result


def get_templates_by_university(university_id: int) -> List[Dict[str, Any]]:
    """Get all templates configured for a university."""
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM templates WHERE university_id = ? ORDER BY created_at DESC",
        (university_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        req_sections = json.loads(r["required_sections"] or "[]")
        rules = json.loads(r["formatting_rules"] or "{}")
        markdown_rules = generate_markdown_rules(r["name"], req_sections, rules)
        result.append({
            "id": r["id"],
            "name": r["name"],
            "description": r["description"] or "",
            "required_sections": req_sections,
            "formatting_rules": rules,
            "markdown_rules": markdown_rules,
            "university_id": r["university_id"],
            "created_by": r["created_by"],
            "created_at": str(r["created_at"])
        })
    return result


def get_templates_by_user(user_id: int) -> List[Dict[str, Any]]:
    """Get templates matching user's university."""
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT university_id FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return []

    university_id = row["university_id"]
    conn.close()
    return get_templates_by_university(university_id)


def get_template_by_id(template_id: Any) -> Dict[str, Any] | None:
    """Retrieve details for a specific template (backward compatible with strings)."""
    init_db()

    # Map legacy string IDs to database integers
    legacy_map = {
        "academic_research": 1,
        "business_report": 2,
        "university_thesis": 3
    }
    db_id = template_id
    if isinstance(template_id, str) and template_id in legacy_map:
        db_id = legacy_map[template_id]

    try:
        db_id = int(db_id)
    except (ValueError, TypeError):
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM templates WHERE id = ?", (db_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    req_sections = json.loads(row["required_sections"] or "[]")
    rules = json.loads(row["formatting_rules"] or "{}")
    markdown_rules = generate_markdown_rules(row["name"], req_sections, rules)

    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "required_sections": req_sections,
        "formatting_rules": rules,
        "markdown_rules": markdown_rules,
        "university_id": row["university_id"],
        "created_by": row["created_by"],
        "created_at": str(row["created_at"])
    }
