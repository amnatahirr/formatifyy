"""
functions/image_ethics.py — Image ethics / appropriateness detector.

Model: claude-sonnet-4-6

Sends each image as base64 to Claude's vision capability and checks for
violent, sexual, personal, or otherwise inappropriate academic content.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from models import Batch

MODEL = "claude-sonnet-4-6"


async def check_image_ethics(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    Evaluate every image in the batch for ethical / academic appropriateness.
    Returns one issue per unethical image.
    """
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
            continue

    return results


async def _evaluate_single_image(
    client: anthropic.AsyncAnthropic,
    image_id: str,
    page: int,
    b64: str,
) -> Dict[str, Any] | None:
    """Send a single image for ethics evaluation."""

    # Detect media type from base64 header or default to png
    media_type = "image/png"
    if b64.startswith("/9j/"):
        media_type = "image/jpeg"
    elif b64.startswith("iVBOR"):
        media_type = "image/png"
    elif b64.startswith("R0lGOD"):
        media_type = "image/gif"

    prompt = """Analyze this image for academic appropriateness. Detect any of the following:
- Weapons or violent imagery
- Sexual or explicit content
- Personal/private photographs (selfies, personal photos not relevant to academics)
- Gore or graphic violence
- Any content inappropriate for an academic document

Return ONLY valid JSON. Do NOT return markdown. Do NOT wrap JSON inside code fences.

Return this exact structure:
{"verdict": "ethical" or "unethical", "reason": "explanation", "confidence": 0-100}

If the image is appropriate for academic use, set verdict to "ethical".
If the image is inappropriate, set verdict to "unethical" and explain why."""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text
    parsed = _safe_parse(raw)
    verdict = parsed.get("verdict", "ethical").lower()

    if verdict == "unethical":
        return {
            "function": "image_ethics",
            "type": "unethical_image",
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
            "confidence": parsed.get("confidence", 0),
            "_replace_image": True,
        }

    return None


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"issues": [], "error": True}
