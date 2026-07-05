"""
functions/para_relevance.py — Paragraph relevance checker.


Checks whether each paragraph belongs under its current heading context.
If a paragraph is misplaced, returns the correct heading it should be under.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from models import Batch

# Import centralized model config — never hardcode the model string
from config import ANALYSIS_MODEL

async def check_para_relevance(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    Check whether each paragraph belongs under its current heading.
    Only checks paragraphs that have a heading context and are body text.
    """
    # Filter to body paragraphs that have a heading context
    relevant = [
        p for p in batch.paragraphs
        if p.heading_context and p.style == "Normal" and len(p.text.split()) > 5
    ]
    if not relevant:
        return []

    paragraphs_payload = [
        {
            "paragraph_id": p.paragraph_id,
            "page": p.page_number,
            "current_heading": p.heading_context,
            "text": p.text[:500],
        }
        for p in relevant
    ]

    # Provide all headings in the batch as context
    all_headings = list(dict.fromkeys(
        p.heading_context for p in batch.paragraphs if p.heading_context
    ))

    prompt = f"""You are an academic document structure expert. For each paragraph below, determine whether it belongs under its current heading or if it should be placed under a different heading.

AVAILABLE HEADINGS IN THIS SECTION:
{json.dumps(all_headings, indent=2)}

PARAGRAPHS TO CHECK:
{json.dumps(paragraphs_payload, indent=2)}

For each paragraph that is MISPLACED (does not belong under its current heading), return:
- "paragraph_id": the paragraph_id
- "page": the page number
- "current_heading": the heading it is currently under
- "correct_heading": the heading it should be under
- "preview": first 100 characters of the paragraph text
- "reason": why it does not belong under the current heading

Only return issues for paragraphs that are clearly misplaced. Do not flag paragraphs that are borderline or ambiguous.

Return ONLY valid JSON. Do NOT return markdown. Do NOT wrap JSON inside code fences.

Return this exact structure:
{{"issues": [...]}}

If all paragraphs are correctly placed, return:
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

        result = []
        for iss in issues:
            result.append({
                "function": "para_relevance",
                "type": "misplaced_paragraph",
                "severity": "major",
                "paragraph_id": iss.get("paragraph_id", ""),
                "image_id": "",
                "page": iss.get("page", 0),
                "reason": iss.get("reason", ""),
                "suggestion": f"Move this paragraph to the \"{iss.get('correct_heading', '')}\" section.",
                "explanation": iss.get("reason", ""),
                "original": "",
                "current_heading": iss.get("current_heading", ""),
                "content_belongs_to": iss.get("correct_heading", ""),
                "text_preview": iss.get("preview", "")[:120],
                "verdict": "misplaced",
                "confidence": 0,
            })
        return result
    except Exception as exc:
        print(f"[para_relevance] error: {exc}")
        return []


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"issues": [], "error": True}
