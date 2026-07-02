"""
functions/image_relevance.py — Image-to-text relevance checker.

Model: claude-sonnet-4-6

Checks whether each image is relevant to the surrounding paragraph text.
The prompt instructs Claude to quote the surrounding text and explain why
the image does or does not belong.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from models import Batch

MODEL = "claude-sonnet-4-6"


async def check_image_relevance(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    For every image in the batch, find its surrounding paragraph text and
    ask Claude whether the image is relevant.
    """
    if not batch.images:
        return []

    # Build a lookup of surrounding text per page
    text_by_page: dict[int, str] = {}
    for p in batch.paragraphs:
        text_by_page.setdefault(p.page_number, "")
        text_by_page[p.page_number] += p.text + "\n"
    # Also include context paragraphs
    for p in batch.context_paragraphs:
        text_by_page.setdefault(p.page_number, "")
        text_by_page[p.page_number] += p.text + "\n"

    results: List[Dict[str, Any]] = []

    for img in batch.images:
        if not img.base64:
            continue
        surrounding = text_by_page.get(img.page_number, "").strip()
        if not surrounding:
            surrounding = "(no surrounding text found)"
        try:
            issue = await _evaluate_relevance(
                client, img.image_id, img.page_number, img.base64, surrounding
            )
            if issue:
                results.append(issue)
        except Exception as exc:
            print(f"[image_relevance] error on {img.image_id}: {exc}")
            continue

    return results


async def _evaluate_relevance(
    client: anthropic.AsyncAnthropic,
    image_id: str,
    page: int,
    b64: str,
    surrounding_text: str,
) -> Dict[str, Any] | None:
    """Check one image against its surrounding text."""

    media_type = "image/png"
    if b64.startswith("/9j/"):
        media_type = "image/jpeg"
    elif b64.startswith("iVBOR"):
        media_type = "image/png"
    elif b64.startswith("R0lGOD"):
        media_type = "image/gif"

    prompt = f"""You are an academic document reviewer. Determine whether the provided image is relevant to the surrounding text in the document.

SURROUNDING TEXT:
\"\"\"{surrounding_text[:2000]}\"\"\"

Instructions:
1. First, quote the most relevant portion of the surrounding text.
2. Describe what the image shows.
3. Explain whether the image is relevant or irrelevant to the quoted text.
4. If irrelevant, explain WHY the image does not belong.

Return ONLY valid JSON. Do NOT return markdown. Do NOT wrap JSON inside code fences.

Return this exact structure:
{{"verdict": "relevant" or "irrelevant", "reason": "detailed explanation quoting the surrounding text", "confidence": 0-100}}"""

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
    verdict = parsed.get("verdict", "relevant").lower()

    if verdict == "irrelevant":
        return {
            "function": "image_relevance",
            "type": "irrelevant_image",
            "severity": "major",
            "paragraph_id": "",
            "image_id": image_id,
            "page": page,
            "reason": parsed.get("reason", "Image is not relevant to surrounding text"),
            "suggestion": "Replace this image with one that matches the surrounding content.",
            "explanation": parsed.get("reason", ""),
            "original": "",
            "current_heading": "",
            "content_belongs_to": "",
            "text_preview": surrounding_text[:120],
            "verdict": "irrelevant",
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
