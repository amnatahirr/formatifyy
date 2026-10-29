"""
Extract a draft Formatify template from a prose formatting-guidelines document.

Pure addition: used only by template_extract_routes.py. Does not alter
manual template create/update flows.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document

from config import ANALYSIS_MODEL

# ── Claude prompt (review carefully before relying on production extracts) ──

EXTRACTION_SYSTEM = """You are an expert academic formatting analyst for Formatify.
You read university / department formatting guideline documents written mostly in prose
(and occasional tables) and convert them into a structured Formatify template draft.

Return ONLY valid JSON. No markdown fences, no commentary."""

EXTRACTION_PROMPT_TEMPLATE = """Read the DOCUMENT TEXT below. It describes formatting rules and required
thesis/report structure in natural language (for example: fonts, margins, spacing,
heading styles, and which chapters/sections are mandatory).

Produce a Formatify template draft with this EXACT JSON shape:

{{
  "name": "string — short template name inferred from the document (university + document type)",
  "description": "string — one-sentence summary of the source guideline",
  "required_sections": [
    {{
      "name": "section title as stated in the document",
      "order": 1,
      "required": true,
      "heading_level": 1
    }}
  ],
  "formatting_rules": {{
    "heading1_font": "Times New Roman",
    "heading1_size": 18,
    "heading1_bold": true,
    "heading1_italic": false,
    "heading1_underline": false,
    "heading1_color": "#000000",
    "heading1_line_spacing": 1.5,
    "heading1_space_before": 12.0,
    "heading1_space_after": 6.0,
    "heading2_font": "Times New Roman",
    "heading2_size": 16,
    "heading2_bold": true,
    "heading2_italic": false,
    "heading2_underline": false,
    "heading2_color": "#000000",
    "heading2_line_spacing": 1.5,
    "heading2_space_before": 10.0,
    "heading2_space_after": 5.0,
    "heading3_font": "Times New Roman",
    "heading3_size": 14,
    "heading3_bold": true,
    "heading3_italic": false,
    "heading3_underline": false,
    "heading3_color": "#000000",
    "heading3_line_spacing": 1.5,
    "heading3_space_before": 8.0,
    "heading3_space_after": 4.0,
    "heading4_font": "Times New Roman",
    "heading4_size": 12,
    "heading4_bold": true,
    "heading4_italic": false,
    "heading4_underline": false,
    "heading4_color": "#000000",
    "heading4_line_spacing": 1.5,
    "heading4_space_before": 6.0,
    "heading4_space_after": 3.0,
    "body_font": "Times New Roman",
    "body_size": 12,
    "body_color": "#000000",
    "body_line_spacing": 2.0,
    "body_space_before": 0.0,
    "body_space_after": 0.0,
    "body_justified": true,
    "bullet_font": "Times New Roman",
    "bullet_size": 12,
    "bullet_color": "#000000",
    "bullet_line_spacing": 2.0,
    "bullet_indent": 0.5,
    "bullet_space_before": 0.0,
    "bullet_space_after": 0.0,
    "bullet_type": "bullet",
    "numbered_font": "Times New Roman",
    "numbered_size": 12,
    "numbered_color": "#000000",
    "numbered_line_spacing": 2.0,
    "numbered_indent": 0.5,
    "numbered_space_before": 0.0,
    "numbered_space_after": 0.0,
    "numbered_style": "1,2,3",
    "heading_numbering_style": "none",
    "page_size": "A4",
    "spacing_unit": "mm",
    "margin_top": 25.0,
    "margin_bottom": 25.0,
    "margin_left": 30.0,
    "margin_right": 20.0,
    "line_number_enabled": false,
    "first_line_indent": 0.5
  }}
}}

RULES FOR required_sections (critical):
1. Extract every distinct chapter / section / front-matter item the guideline lists
   as part of the document structure (Title Page, Abstract, Introduction, etc.).
2. Set "required": true when the document marks the section as mandatory using
   words such as: MANDATORY, Mandatory, REQUIRED, Required, must include,
   must be included, compulsory, obligatory, shall include, is required.
3. Set "required": false when the document marks it optional using words such as:
   OPTIONAL, Optional, if applicable, may be included, can be included,
   not mandatory, where relevant.
4. If a section appears in a required outline / table of contents structure but is
   NOT explicitly labeled optional, default "required": true.
5. "order" is 1-based in document order (appearance in the guideline’s structure list).
6. "heading_level" is 1–4:
   - Top-level chapters / main sections → 1
   - Explicit subsections under a main section → 2 (or deeper if clearly stated)
   - Front matter treated as top-level section titles → 1 unless the guideline says otherwise
7. Use the section’s official name from the guideline (prefer exact wording).

RULES FOR formatting_rules:
1. Prefer explicit numeric values stated in the document (pt, inches, mm, cm, lines).
2. Convert units into the JSON fields above:
   - Font sizes → integer points (heading*_size, body_size)
   - Margins → numbers in millimetres when the doc uses mm/cm; if inches, convert to mm
     (1 inch = 25.4 mm) and set spacing_unit to "mm"
   - Line spacing → float (e.g. double → 2.0, 1.5 → 1.5)
   - first_line_indent → inches as a float when stated in inches (Formatify form expects inches here)
3. Map “Main Heading / Chapter Heading” → heading1_*; “Sub-heading” → heading2_*;
   “Sub-sub-heading” → heading3_* when those labels are used.
4. Bold/italic/underline: set booleans only when the document clearly requires them.
5. heading_numbering_style: "decimal" if numbered 1 / 1.1 / 1.1.1; "roman" or "alpha"
   only if clearly stated; otherwise "none".
6. If a value is not stated, keep the default shown in the schema above — do NOT invent
   university-specific numbers that are not in the text.
7. Omit table_style and reference_rules unless the document clearly specifies them;
   if omitted, the admin form will keep its own defaults.

DOCUMENT TEXT:
\"\"\"
{document_text}
\"\"\"

Return ONLY the JSON object."""


def extract_text_from_docx(file_path: str) -> str:
    """Pull plain paragraph text from a .docx (tables appended as cell rows)."""
    doc = Document(file_path)
    parts: List[str] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if text:
            parts.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [(c.text or "").strip() for c in row.cells]
            cells = [c for c in cells if c]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def _safe_parse_json(raw: str) -> Dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?\s*", "", (raw or "").strip()).rstrip("`").strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(cleaned[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("Claude did not return valid JSON for the template draft")


def _normalize_draft(data: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Claude output into the shape the Create Template form expects."""
    name = str(data.get("name") or "Extracted Template").strip() or "Extracted Template"
    description = str(data.get("description") or "").strip()

    sections_out: List[Dict[str, Any]] = []
    raw_sections = data.get("required_sections") or []
    if isinstance(raw_sections, list):
        for idx, sec in enumerate(raw_sections):
            if isinstance(sec, str):
                sections_out.append(
                    {
                        "name": sec.strip(),
                        "order": idx + 1,
                        "required": True,
                        "heading_level": 1,
                    }
                )
                continue
            if not isinstance(sec, dict):
                continue
            sec_name = str(sec.get("name") or "").strip()
            if not sec_name:
                continue
            try:
                level = int(sec.get("heading_level") or sec.get("headingLevel") or 1)
            except (TypeError, ValueError):
                level = 1
            level = max(1, min(4, level))
            required = sec.get("required")
            if required is None:
                required = True
            sections_out.append(
                {
                    "name": sec_name,
                    "order": int(sec.get("order") or idx + 1),
                    "required": bool(required),
                    "heading_level": level,
                }
            )

    rules = data.get("formatting_rules") or {}
    if not isinstance(rules, dict):
        rules = {}

    return {
        "name": name,
        "description": description,
        "required_sections": sections_out,
        "formatting_rules": rules,
    }


async def extract_template_draft_from_docx(
    client: Any,
    file_bytes: bytes,
    filename: str,
) -> Dict[str, Any]:
    """
    Run Claude over DOCX prose and return a normalized template draft dict.
    """
    suffix = Path(filename or "upload.docx").suffix.lower() or ".docx"
    if suffix != ".docx":
        raise ValueError("Only .docx files are supported for template extraction")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        document_text = extract_text_from_docx(tmp_path)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass

    if not document_text or len(document_text.strip()) < 40:
        raise ValueError("Document contains too little text to extract formatting rules")

    # Cap extremely long guidelines to keep the prompt manageable
    if len(document_text) > 60000:
        document_text = document_text[:60000] + "\n\n[Document truncated for length]"

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(document_text=document_text)

    response = await client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=4096,
        system=EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text if response.content else ""
    parsed = _safe_parse_json(raw)
    return _normalize_draft(parsed)
