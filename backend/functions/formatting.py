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
            "text": p.text[:300],
        }
        for p in batch.paragraphs
    ]

    prompt = f"""You are a document formatting expert. Compare the following paragraphs against the provided formatting template and identify any violations.

TEMPLATE RULES:
{template_rules}

DOCUMENT PARAGRAPHS:
{json.dumps(paragraphs_payload, indent=2)}

For each formatting violation found, return a JSON object with:
- "paragraph_id": the paragraph_id where the violation occurs
- "page": the page number
- "type": the type of violation (e.g., "heading_style", "spacing", "font", "section_order", "missing_section", "alignment", "margin")
- "reason": what rule is violated and why
- "suggestion": how to fix it
- "severity": "major" if it significantly deviates from the template, "minor" otherwise

Also return a "compliance_score" from 0 to 100 representing overall formatting compliance for this batch.

Return ONLY valid JSON. Do NOT return markdown. Do NOT wrap JSON inside code fences.

Return this exact structure:
{{"issues": [...], "compliance_score": 85}}

If no issues are found, return:
{{"issues": [], "compliance_score": 100}}

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
            result.append({
                "function": "formatting",
                "type": iss.get("type", "formatting"),
                "severity": iss.get("severity", "minor"),
                "paragraph_id": iss.get("paragraph_id", ""),
                "image_id": "",
                "page": iss.get("page", 0),
                "reason": iss.get("reason", ""),
                "suggestion": iss.get("suggestion", ""),
                "explanation": iss.get("reason", ""),
                "original": "",
                "current_heading": "",
                "content_belongs_to": "",
                "text_preview": "",
                "verdict": "",
                "confidence": compliance_score,
                "_compliance_score": compliance_score,
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
