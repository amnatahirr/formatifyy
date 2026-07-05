"""
functions/grammar.py — Grammar, spelling, and punctuation checker.

Model: claude-haiku-4-5-20251001
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from models import Batch, Issue

# Import centralized model config — never hardcode the model string
from config import ANALYSIS_MODEL


async def check_grammar(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    Send every paragraph in the batch to Claude for grammar / spelling /
    punctuation analysis.  Returns a list of raw issue dicts.
    """
    if not batch.paragraphs:
        return []

    paragraphs_payload = [
        {
            "paragraph_id": p.paragraph_id,
            "page": p.page_number,
            "text": p.text,
        }
        for p in batch.paragraphs
    ]

    prompt = f"""You are a professional proofreader. Analyze the following paragraphs for grammar, spelling, and punctuation errors.

PARAGRAPHS:
{json.dumps(paragraphs_payload, indent=2)}

For each error found, return a JSON object with these fields:
- "paragraph_id": the paragraph_id where the error occurs
- "page": the page number
- "original": the exact text that contains the error
- "suggestion": the corrected version
- "reason": brief explanation of the error
- "severity": "major" if the error changes meaning or is very noticeable, "minor" otherwise

Return ONLY valid JSON. Do NOT return markdown. Do NOT wrap JSON inside code fences.

Return this exact structure:
{{"issues": [...]}}

If no errors are found, return:
{{"issues": []}}

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
        # Normalise into Issue-compatible dicts
        result = []
        for iss in issues:
            result.append({
                "function": "grammar",
                "type": "grammar",
                "severity": iss.get("severity", "minor"),
                "paragraph_id": iss.get("paragraph_id", ""),
                "image_id": "",
                "page": iss.get("page", 0),
                "reason": iss.get("reason", ""),
                "suggestion": iss.get("suggestion", ""),
                "explanation": iss.get("reason", ""),
                "original": iss.get("original", ""),
                "current_heading": "",
                "content_belongs_to": "",
                "text_preview": iss.get("original", "")[:120],
                "verdict": "",
                "confidence": 0,
            })
        return result
    except Exception as exc:
        print(f"[grammar] error: {exc}")
        return []


# ─── JSON helpers ─────────────────────────────────────────────────────────────

def _safe_parse(text: str) -> dict:
    """Strip markdown fences and parse JSON safely."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"issues": [], "error": True}
