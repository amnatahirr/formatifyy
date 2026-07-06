"""
functions/formatting.py — Formatting compliance checker.

Model: claude-haiku-4-5-20251001

Compares the document structure against the selected markdown template
by injecting every rule into the prompt.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from models import Batch

# Import centralized model config — never hardcode the model string
from config import ANALYSIS_MODEL


async def check_formatting(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
    template_rules: str,
) -> List[Dict[str, Any]]:
    """
    Compare batch paragraphs against the template rules.
    Returns a list of raw issue dicts plus a compliance_score.
    """
    if not batch.paragraphs:
        return []

    paragraphs_payload = [
        {
            "paragraph_id": p.paragraph_id,
            "page": p.page_number,
            "style": p.style,
            "heading_context": p.heading_context,
            "text": p.text[:400],
        }
        for p in batch.paragraphs
    ]

    prompt = f"""You are a strict academic document formatting auditor. Compare each paragraph against the template specification below.

TEMPLATE SPECIFICATION (authoritative — every rule must be enforced):
{template_rules}

DOCUMENT PARAGRAPHS (from the student's file):
{json.dumps(paragraphs_payload, indent=2)}

AUDIT RULES:
1. You must NEVER rewrite, summarize, or replace paragraph content. Only identify structural issues. The original text is sacred.
2. The "suggestion" field must describe WHAT TO DO (e.g. "Apply Heading 1 style") — NEVER put replacement paragraph text in suggestion.
3. Section titles MUST use Word style "Heading 1/2/3" — NOT just bold Normal text.
4. Every issue MUST reference an existing paragraph_id from the input.
5. For heading_style issues, include heading_level (1-4) from the template.

For each violation return:
- "paragraph_id": exact paragraph_id from input (required)
- "page": page number
- "type": one of heading_style, section_order, missing_section, font, spacing, alignment, margin
- "problem": what rule is violated (do NOT repeat paragraph text as a fix)
- "reason": same as problem — what is wrong structurally
- "suggestion": instruction only (e.g. "Apply Heading 1 style to this section title")
- "heading_level": integer 1-4 (required when type is heading_style)
- "original": copy of paragraph text exactly as-is
- "severity": "major" or "minor"

Return ONLY valid JSON:
{{"issues": [...], "compliance_score": 72, "summary": "Document is 72% compliant with template"}}

If no issues: {{"issues": [], "compliance_score": 100, "summary": "Fully compliant"}}

Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the raw JSON."""

    try:
        response = await client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        parsed = _safe_parse(raw)
        issues = parsed.get("issues", [])
        compliance_score = parsed.get("compliance_score", 100)

        result = []
        for iss in issues:
            issue_type = iss.get("type", "formatting")
            heading_level = int(float(iss.get("heading_level", 1) or 1))
            suggestion = iss.get("suggestion", "") or iss.get("problem", "")
            reason = iss.get("reason", "") or iss.get("problem", "")
            if issue_type == "heading_style" and not suggestion:
                suggestion = f"Apply Heading {heading_level} style to this section title"

            result.append({
                "function": "formatting",
                "type": issue_type,
                "severity": iss.get("severity", "minor"),
                "paragraph_id": iss.get("paragraph_id", ""),
                "image_id": "",
                "page": iss.get("page", 0),
                "reason": reason,
                "suggestion": suggestion,
                "explanation": reason,
                "original": iss.get("original", ""),
                "heading_level": heading_level,
                "current_heading": "",
                "content_belongs_to": "",
                "text_preview": (iss.get("original") or "")[:120],
                "verdict": "",
                "confidence": int(float(compliance_score or 0)),
                "_compliance_score": int(float(compliance_score or 0)),
            })
        return result
    except Exception as exc:
        print(f"[formatting] error: {exc}")
        return []


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"issues": [], "error": True}
