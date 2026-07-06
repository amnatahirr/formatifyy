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

from config import ANALYSIS_MODEL


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

    prompt = f"""You are a strict academic document reviewer. Determine whether the provided image is relevant to the surrounding text in the document.

SURROUNDING TEXT:
\"\"\"{surrounding_text[:2000]}\"\"\"

Instructions:
1. Quote the most relevant portion of the surrounding text.
2. Describe what the image shows.
3. Compare the image subject to the section topic — flag as irrelevant if they are clearly different domains (e.g. house photo in a computer architecture section, random stock photo, unrelated diagram).
4. When the image does not directly support or illustrate the surrounding text, set verdict to "irrelevant".

Return ONLY valid JSON. Do NOT return markdown. Do NOT wrap JSON inside code fences.

Return this exact structure:
{{"verdict": "relevant" or "irrelevant", "reason": "detailed explanation quoting the surrounding text", "confidence": 0-100}}

Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the raw JSON."""

    response = await client.messages.create(
        model=ANALYSIS_MODEL,
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
            "type": "image_relevance",
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
            "surrounding_text": surrounding_text[:200],
            "text_preview": surrounding_text[:120],
            "verdict": "irrelevant",
            "confidence": int(float(parsed.get("confidence", 0) or 0)),
            "_replace_image": True,
        }

    return None


async def evaluate_image_relevance(
    client: anthropic.AsyncAnthropic,
    b64: str,
    surrounding_text: str,
) -> Dict[str, Any]:
    """Return relevance verdict for a single image (used after replacement)."""
    if not b64:
        return {
            "verdict": "relevant",
            "is_relevant": True,
            "confidence": 0.5,
            "reason": "Could not read image bytes for validation.",
        }

    media_type = "image/png"
    if b64.startswith("/9j/"):
        media_type = "image/jpeg"

    prompt = f"""You are a strict academic document reviewer. Determine whether the provided image is relevant to the surrounding text.

SURROUNDING TEXT:
\"\"\"{surrounding_text[:2000]}\"\"\"

Return ONLY valid JSON:
{{"verdict": "relevant" or "irrelevant", "reason": "brief explanation", "confidence": 0-100}}"""

    response = await client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    parsed = _safe_parse(response.content[0].text)
    verdict = str(parsed.get("verdict", "relevant")).lower()
    conf = float(parsed.get("confidence", 80) or 80)
    if conf > 1.0:
        conf = conf / 100.0
    return {
        "verdict": verdict,
        "is_relevant": verdict != "irrelevant",
        "confidence": conf,
        "reason": parsed.get("reason", ""),
    }


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"verdict": "relevant", "reason": "Parse error", "confidence": 0}


async def recheck_image(
    client: anthropic.AsyncAnthropic,
    b64: str,
    surrounding_text: str,
    image_id: str = "",
) -> Dict[str, Any]:
    """Run ethics + relevance on a single replacement image."""
    from functions.image_ethics import evaluate_image_ethics

    ethics = await evaluate_image_ethics(client, b64)
    relevance = await evaluate_image_relevance(client, b64, surrounding_text)
    cleared = bool(ethics.get("is_ethical")) and bool(relevance.get("is_relevant"))
    return {
        "image_id": image_id,
        "ethics": ethics,
        "relevance": relevance,
        "cleared": cleared,
        "is_relevant": relevance.get("is_relevant", False),
        "is_ethical": ethics.get("is_ethical", True),
        "confidence": relevance.get("confidence", 0),
    }
