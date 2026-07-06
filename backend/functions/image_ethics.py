"""
functions/image_ethics.py — Image ethics / appropriateness detector.

Model: claude-haiku-4-5-20251001 (via config.ANALYSIS_MODEL)
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from config import ANALYSIS_MODEL
from models import Batch


def _media_type(b64: str) -> str:
    if b64.startswith("/9j/"):
        return "image/jpeg"
    if b64.startswith("R0lGOD"):
        return "image/gif"
    if b64.startswith("UklGR"):
        return "image/webp"
    return "image/png"


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"verdict": "ethical", "reason": "Parse error", "confidence": 0}


async def evaluate_image_ethics(
    client: anthropic.AsyncAnthropic,
    b64: str,
) -> Dict[str, Any]:
    """Single-image ethics check (used after user replaces an image)."""
    if not b64:
        return {"verdict": "ethical", "is_ethical": True, "confidence": 0, "reason": "No image data"}

    prompt = """Analyze this image for academic appropriateness. Detect:
- Weapons or violent imagery
- Sexual or explicit content
- Personal/private photographs inappropriate for academics
- Gore or graphic violence

Return ONLY valid JSON:
{"verdict": "ethical" or "unethical", "reason": "explanation", "confidence": 0-100}

Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the raw JSON."""

    response = await client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": _media_type(b64), "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    parsed = _safe_parse(response.content[0].text)
    verdict = str(parsed.get("verdict", "ethical")).lower()
    conf = int(float(parsed.get("confidence", 0) or 0))
    return {
        "verdict": verdict,
        "is_ethical": verdict != "unethical",
        "confidence": conf,
        "reason": parsed.get("reason", ""),
    }


async def check_image_ethics(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """Evaluate every image in the batch for ethical / academic appropriateness."""
    if not batch.images:
        return []

    results: List[Dict[str, Any]] = []
    for img in batch.images:
        if not img.base64:
            continue
        try:
            issue = await _evaluate_single_image(client, img.image_id, img.page_number, img.base64)
            if issue:
                results.append(issue)
        except Exception as exc:
            print(f"[image_ethics] error on {img.image_id}: {exc}")
    return results


async def _evaluate_single_image(
    client: anthropic.AsyncAnthropic,
    image_id: str,
    page: int,
    b64: str,
) -> Dict[str, Any] | None:
    prompt = """Analyze this image for academic appropriateness. Detect any of the following:
- Weapons or violent imagery
- Sexual or explicit content
- Personal/private photographs (selfies, personal photos not relevant to academics)
- Gore or graphic violence
- Any content inappropriate for an academic document

Return ONLY valid JSON:
{"verdict": "ethical" or "unethical", "reason": "explanation", "confidence": 0-100}

If appropriate, verdict is "ethical". If inappropriate, verdict is "unethical".

Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the raw JSON."""

    response = await client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": _media_type(b64), "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    parsed = _safe_parse(response.content[0].text)
    verdict = str(parsed.get("verdict", "ethical")).lower()

    if verdict == "unethical":
        return {
            "function": "image_ethics",
            "type": "image_ethics",
            "severity": "major",
            "paragraph_id": "",
            "image_id": image_id,
            "page": page,
            "reason": parsed.get("reason", "Image flagged as inappropriate"),
            "suggestion": "Replace this image with appropriate academic content.",
            "explanation": parsed.get("reason", ""),
            "original": "",
            "current_heading": "",
            "content_belongs_to": "",
            "text_preview": "",
            "verdict": "unethical",
            "confidence": int(float(parsed.get("confidence", 0) or 0)),
            "_replace_image": True,
        }
    return None
