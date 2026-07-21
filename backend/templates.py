"""
templates.py — Predefined and dynamic formatting templates for Formatify.

Integrates with sqlite database (database.py) to load, store, delete,
and retrieve templates. Converts JSON template specifications into the
exact markdown rules prompt injected into LLM checkers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from database import get_db


def _margin_display_inches(value: float) -> float:
    """Convert stored margin (mm if > 3) to inches for display/prompts."""
    v = float(value)
    return round(v / 25.4, 2) if v > 3.0 else v


def generate_markdown_rules(name: str, required_sections: List[str], rules: Dict[str, Any]) -> str:
    """
    Dynamically translate database-stored templates (JSON config) into a single
    markdown rules prompt. Matches what LLMs and python-docx expect.
    """
    sections_text = "\n".join(
        f"- Section {idx + 1}: **{sec.get('name', sec) if isinstance(sec, dict) else sec}** "
        f"→ MUST use Word style **Heading {sec.get('heading_level', 1) if isinstance(sec, dict) else 1}**"
        for idx, sec in enumerate(required_sections)
    )

    numbering = rules.get("heading_numbering", "decimal")
    numbering_note = (
        "Section titles MUST be numbered as '1. Section Name', '2. Section Name', etc."
        if numbering == "decimal"
        else "Section titles should NOT use decimal numbering."
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
    first_line_indent = _margin_display_inches(rules.get("first_line_indent", 0.5))

    margin_top = _margin_display_inches(rules.get("margin_top", 1.0))
    margin_bottom = _margin_display_inches(rules.get("margin_bottom", 1.0))
    margin_left = _margin_display_inches(rules.get("margin_left", 1.0))
    margin_right = _margin_display_inches(rules.get("margin_right", 1.0))
    page_size = rules.get("page_size", "A4")

    return f"""# {name} — Formatting Specification

## Required Document Sections (strict order)
{sections_text}

{numbering_note}

Each section title paragraph MUST:
1. Use the exact Word built-in style "Heading N" (not just bold text)
2. Appear in the order listed above
3. Match the section name (numbering prefix optional)

## Heading Styles (Word built-in styles)
- **Heading 1**: {h1_style} — use for main chapter/section titles
- **Heading 2**: {h2_style} — use for subsections
- **Heading 3**: {h3_style} — use for sub-subsections

## Body Text (Normal style)
- Font: {body_font}, {body_size}pt
- Line Spacing: {body_line_spacing}
- Space Before: {body_space_before}pt
- Space After: {body_space_after}pt
- First Line Indent: {first_line_indent} inches (first paragraph after a heading has NO indent)

## Page Layout
- Margins: Top {margin_top} in, Bottom {margin_bottom} in, Left {margin_left} in, Right {margin_right} in
- Page Size: {page_size}

## Violation types to detect
- heading_style: paragraph is a section title but uses Normal/bold instead of Heading N
- section_order: sections appear in wrong order or are missing
- font: wrong font family or size
- spacing: wrong line spacing or paragraph spacing
- alignment: wrong text alignment
- margin: page margins incorrect
"""


def get_all_templates() -> List[Dict[str, Any]]:
    """Return all templates for general listing."""
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
            "department_id": r["department_id"] if "department_id" in r.keys() else None,
            "created_by": r["created_by"],
            "created_at": str(r["created_at"])
        })
    return result


def get_templates_by_university(university_id: int) -> List[Dict[str, Any]]:
    """Get all templates configured for a university."""
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
            "department_id": r["department_id"] if "department_id" in r.keys() else None,
            "created_by": r["created_by"],
            "created_at": str(r["created_at"])
        })
    return result


def get_templates_by_user(user_id: int) -> List[Dict[str, Any]]:
    """Get templates matching user's university."""
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


def update_template(template_id: int, updates: Dict[str, Any]) -> Dict[str, Any] | None:
    """Update an existing template. Returns the updated template or None."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM templates WHERE id = ?", (template_id,))
    if not cursor.fetchone():
        conn.close()
        return None

    fields = []
    values: list = []
    if updates.get("name") is not None:
        fields.append("name = ?")
        values.append(updates["name"])
    if updates.get("description") is not None:
        fields.append("description = ?")
        values.append(updates["description"])
    if updates.get("required_sections") is not None:
        fields.append("required_sections = ?")
        values.append(json.dumps(updates["required_sections"]))
    if updates.get("formatting_rules") is not None:
        fields.append("formatting_rules = ?")
        values.append(json.dumps(updates["formatting_rules"]))
    if "department_id" in updates:
        fields.append("department_id = ?")
        values.append(updates["department_id"])

    if not fields:
        conn.close()
        return get_template_by_id(template_id)

    values.append(template_id)
    cursor.execute(
        f"UPDATE templates SET {', '.join(fields)} WHERE id = ?",
        values,
    )
    conn.commit()
    conn.close()
    return get_template_by_id(template_id)


def get_template_by_id(template_id: Any) -> Dict[str, Any] | None:
    """Retrieve details for a specific template (backward compatible with strings)."""
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
        "department_id": row["department_id"] if "department_id" in row.keys() else None,
        "created_by": row["created_by"],
        "created_at": str(row["created_at"])
    }
