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

    prompt = f"""You are a professional proofreader for academic documents. Find grammar, spelling, and punctuation errors.

PARAGRAPHS:
{json.dumps(paragraphs_payload, indent=2)}

RULES:
1. "original" MUST be an exact verbatim substring copied from the paragraph's "text" field (character-for-character).
2. "suggestion" is the same substring with only the error corrected.
3. If an entire sentence is wrong, set "original" to the full sentence and "suggestion" to the corrected sentence.
4. Every issue MUST include the correct paragraph_id from the input.
5. Do not flag stylistic preferences — only clear errors.

For each error return:
- "paragraph_id": from input
- "page": page number
- "original": exact substring from paragraph text
- "suggestion": corrected substring
- "reason": brief explanation
- "severity": "major" if meaning changes, else "minor"

Return ONLY valid JSON:
{{"issues": [...]}}

If no errors: {{"issues": []}}

No markdown, no code fences — raw JSON only."""

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
