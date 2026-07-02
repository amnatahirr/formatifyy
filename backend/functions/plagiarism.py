"""
functions/plagiarism.py — Pattern-based plagiarism / AI-writing detector.

Model: claude-opus-4-7

NO INTERNET access. Detects plagiarism indicators purely from text patterns:
- Writing style shifts
- Boilerplate / filler text
- Generic AI-generated writing patterns
- Unattributed quotations
- Terminology inconsistencies within the document
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from models import Batch

MODEL = "claude-opus-4-7"


async def check_plagiarism(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    Analyze paragraphs for plagiarism indicators.
    Returns a list of issue dicts plus an overall risk_score per flagged paragraph.
    """
    # Only analyse body paragraphs with enough content
    relevant = [
        p for p in batch.paragraphs
        if p.style == "Normal" and len(p.text.split()) > 10
    ]
    if not relevant:
        return []

    paragraphs_payload = [
        {
            "paragraph_id": p.paragraph_id,
            "page": p.page_number,
            "heading_context": p.heading_context,
            "text": p.text[:600],
        }
        for p in relevant
    ]

    prompt = f"""You are an academic integrity expert. Analyze the following paragraphs for plagiarism indicators. You do NOT have internet access — analyze text patterns only.

PARAGRAPHS:
{json.dumps(paragraphs_payload, indent=2)}

Detect these specific patterns:
1. Writing style shifts — sudden changes in vocabulary, tone, or complexity between consecutive paragraphs
2. Boilerplate text — generic filler phrases that add no substance
3. AI-generated writing patterns — overly perfect structure, repetitive transitions, lack of personal voice
4. Unattributed quotations — text that appears to be quoted but has no citation
5. Terminology inconsistencies — using different terms for the same concept within the document

For each issue found, return:
- "paragraph_id": the paragraph_id
- "page": the page number
- "type": one of "style_shift", "boilerplate", "ai_writing", "unattributed_quote", "terminology_inconsistency"
- "reason": detailed explanation
- "risk_score": 0-100 indicating how likely this is plagiarized or AI-generated
- "text_preview": the specific text fragment that is suspicious
- "severity": "major" if risk_score >= 70, "minor" otherwise

Return ONLY valid JSON. Do NOT return markdown. Do NOT wrap JSON inside code fences.

Return this exact structure:
{{"issues": [...], "overall_risk": 0-100}}

If no issues are found, return:
{{"issues": [], "overall_risk": 0}}"""

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        parsed = _safe_parse(raw)
        issues = parsed.get("issues", [])
        overall_risk = parsed.get("overall_risk", 0)

        result = []
        for iss in issues:
            risk = iss.get("risk_score", 0)
            result.append({
                "function": "plagiarism",
                "type": iss.get("type", "plagiarism"),
                "severity": iss.get("severity", "major" if risk >= 70 else "minor"),
                "paragraph_id": iss.get("paragraph_id", ""),
                "image_id": "",
                "page": iss.get("page", 0),
                "reason": iss.get("reason", ""),
                "suggestion": "Review this paragraph for originality and add proper citations if needed.",
                "explanation": iss.get("reason", ""),
                "original": "",
                "current_heading": "",
                "content_belongs_to": "",
                "text_preview": iss.get("text_preview", "")[:120],
                "verdict": f"risk_score={risk}",
                "confidence": risk,
                "_risk_score": risk,
                "_overall_risk": overall_risk,
            })
        return result
    except Exception as exc:
        print(f"[plagiarism] error: {exc}")
        return []


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"issues": [], "error": True}
