"""
functions/image_relevance.py — Local image–section relevance detector.

Runs fully offline (no Claude / GPT / Gemini APIs).

Optimisations vs first version:
  - CLIP similarity only (no second BLIP caption pass by default)
  - Reuses cached BLIP caption for light keyword bonus when available
  - Images downscaled in local_vision before inference
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

from models import Batch
from functions.local_vision import (
    clip_similarity_from_b64,
    generate_caption_from_b64,
    image_fingerprint,
)


DEFAULT_RELEVANCE_THRESHOLD = 0.22
_KEYWORD_BONUS_MAX = 0.08


def _build_section_text(heading: str, paragraph: str) -> str:
    parts = [p.strip() for p in (heading or "", paragraph or "") if p and p.strip()]
    return " ".join(parts).strip() or "empty document section"


def _extract_keywords(text: str) -> set:
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "are", "was", "has",
        "have", "its", "into", "also", "below", "above", "following", "shows",
        "shown", "figure", "image", "diagram", "each", "used", "uses", "using",
        "based", "which", "their", "they", "them", "then", "than", "when",
        "where", "how", "all", "any", "can", "may", "will", "two", "one",
        "data", "system", "process", "result", "results", "report",
    }
    words = set(re.findall(r"\b[a-zA-Z]{4,}\b", (text or "").lower()))
    return words - stop


def analyze_image_relevance_sync(
    b64: str,
    heading: str = "",
    paragraph: str = "",
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    caption: str | None = None,
    skip_caption: bool = False,
) -> dict:
    """
    Local CLIP relevance analysis.

    Returns: { "similarity": float, "relevant": bool, ... }
    """
    if not b64:
        return {
            "similarity": 0.0,
            "relevant": False,
            "is_relevant": False,
            "verdict": "irrelevant",
            "confidence": 0.0,
            "reason": "No image data",
            "caption": "",
        }

    section_text = _build_section_text(heading, paragraph)
    similarity = clip_similarity_from_b64(b64, section_text)

    # Reuse cached caption for keyword bonus — never force a second BLIP run
    # unless caption was already produced by ethics in the same combined pass.
    if caption is None and not skip_caption:
        try:
            caption = generate_caption_from_b64(b64, cache_key=image_fingerprint(b64))
        except Exception as exc:
            print(f"[image_relevance] caption skipped: {exc}")
            caption = ""

    caption = caption or ""
    keyword_bonus = 0.0
    matches: list = []
    if caption:
        img_kw = _extract_keywords(caption)
        ctx_kw = _extract_keywords(section_text)
        matches = sorted(img_kw & ctx_kw)
        if matches:
            keyword_bonus = min(_KEYWORD_BONUS_MAX, 0.03 * len(matches))

    final_score = min(1.0, similarity + keyword_bonus)
    relevant = final_score >= threshold

    reason = (
        f"CLIP similarity={similarity:.3f}"
        + (f", keyword_bonus={keyword_bonus:.3f} matches={matches}" if matches else "")
        + f" vs threshold={threshold:.2f}."
        + (f" Caption: '{caption}'." if caption else "")
    )

    if relevant:
        print(
            f"[image_relevance] ✅ RELEVANT | similarity={final_score:.3f} | "
            f"heading='{(heading or '')[:60]}' | caption='{caption[:80]}'"
        )
    else:
        print(
            f"[image_relevance] ❌ IRRELEVANT | similarity={final_score:.3f} | "
            f"threshold={threshold:.2f} | heading='{(heading or '')[:60]}' | "
            f"caption='{caption[:80]}'"
        )

    return {
        "similarity": round(final_score, 4),
        "clip_similarity": round(similarity, 4),
        "relevant": relevant,
        "is_relevant": relevant,
        "verdict": "relevant" if relevant else "irrelevant",
        "confidence": round(final_score, 4),
        "threshold": threshold,
        "caption": caption,
        "heading": heading,
        "keyword_matches": matches,
        "reason": reason,
    }


def _surrounding_for_image(batch: Batch, page_number: int) -> tuple[str, str]:
    candidates = list(batch.paragraphs) + list(batch.context_paragraphs)
    same_page = [p for p in candidates if p.page_number == page_number]
    pool = same_page or candidates

    heading = ""
    for p in pool:
        if p.heading_context and p.heading_context.strip():
            heading = p.heading_context.strip()
            break

    body_parts: list[str] = []
    for p in pool:
        t = (p.text or "").strip()
        if t:
            body_parts.append(t)
        if len(body_parts) >= 6:
            break

    return heading, " ".join(body_parts)


# ======================================================================
# PIPELINE API
# ======================================================================

async def evaluate_image_relevance(
    client: Any = None,
    b64: str = "",
    surrounding_text: str = "",
    heading: str = "",
) -> Dict[str, Any]:
    paragraph = surrounding_text or ""
    if not heading and paragraph:
        lines = [ln.strip() for ln in paragraph.splitlines() if ln.strip()]
        if lines and len(lines[0].split()) <= 12:
            heading = lines[0]
            paragraph = " ".join(lines[1:]) if len(lines) > 1 else paragraph

    result = await asyncio.to_thread(
        analyze_image_relevance_sync, b64, heading, paragraph
    )
    return {
        "verdict": result["verdict"],
        "is_relevant": result["relevant"],
        "relevant": result["relevant"],
        "similarity": result["similarity"],
        "confidence": float(result["similarity"]),
        "reason": result["reason"],
        "caption": result.get("caption", ""),
    }


async def check_image_relevance(
    client: Any,
    batch: Batch,
) -> List[Dict[str, Any]]:
    if not batch.images:
        return []

    results: List[Dict[str, Any]] = []
    for img in batch.images:
        if not img.base64:
            continue
        heading, paragraph = _surrounding_for_image(batch, img.page_number)
        try:
            issue = await _evaluate_relevance(
                img.image_id, img.page_number, img.base64, heading, paragraph
            )
            if issue:
                results.append(issue)
        except Exception as exc:
            print(f"[image_relevance] error on {img.image_id}: {exc}")
            continue
    return results


async def _evaluate_relevance(
    image_id: str,
    page: int,
    b64: str,
    heading: str,
    paragraph: str,
    caption: str | None = None,
) -> Optional[Dict[str, Any]]:
    result = await asyncio.to_thread(
        lambda: analyze_image_relevance_sync(
            b64,
            heading=heading,
            paragraph=paragraph,
            caption=caption,
            skip_caption=False,
        )
    )
    if result["relevant"]:
        return None

    conf = result["similarity"]
    conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(conf)
    surrounding = _build_section_text(heading, paragraph)

    return {
        "function": "image_relevance",
        "type": "image_relevance",
        "severity": "major",
        "paragraph_id": "",
        "image_id": image_id,
        "page": page,
        "reason": result["reason"],
        "suggestion": "Replace this image with one that matches the surrounding content.",
        "explanation": result["reason"],
        "original": "",
        "current_heading": heading,
        "content_belongs_to": "",
        "surrounding_text": surrounding[:200],
        "text_preview": surrounding[:120],
        "verdict": "irrelevant",
        "similarity": result["similarity"],
        "confidence": conf_pct,
        "relevant": False,
        "_replace_image": True,
    }


async def check_images_combined(
    client: Any,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    Single pass over batch images: one BLIP caption + one CLIP score.
    Returns both ethics and relevance issues.
    """
    from functions.image_ethics import analyze_image_ethics_sync

    if not batch.images:
        return []

    def _process_all() -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        for img in batch.images:
            if not img.base64:
                continue
            heading, paragraph = _surrounding_for_image(batch, img.page_number)
            try:
                ethics = analyze_image_ethics_sync(img.base64)
                if not ethics["ethical"]:
                    conf = ethics["confidence"]
                    conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(conf)
                    issues.append({
                        "function": "image_ethics",
                        "type": "image_ethics",
                        "severity": "major",
                        "paragraph_id": "",
                        "image_id": img.image_id,
                        "page": img.page_number,
                        "reason": ethics["reason"],
                        "suggestion": "Replace this image with appropriate academic content.",
                        "explanation": ethics["reason"],
                        "original": "",
                        "current_heading": heading,
                        "content_belongs_to": "",
                        "text_preview": ethics.get("caption", "")[:120],
                        "verdict": "unethical",
                        "ethics_category": ethics["category"],
                        "confidence": conf_pct,
                        "ethical": False,
                        "_replace_image": True,
                    })

                rel = analyze_image_relevance_sync(
                    img.base64,
                    heading=heading,
                    paragraph=paragraph,
                    caption=ethics.get("caption") or "",
                    skip_caption=True,
                )
                if not rel["relevant"]:
                    conf = rel["similarity"]
                    conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(conf)
                    surrounding = _build_section_text(heading, paragraph)
                    issues.append({
                        "function": "image_relevance",
                        "type": "image_relevance",
                        "severity": "major",
                        "paragraph_id": "",
                        "image_id": img.image_id,
                        "page": img.page_number,
                        "reason": rel["reason"],
                        "suggestion": "Replace this image with one that matches the surrounding content.",
                        "explanation": rel["reason"],
                        "original": "",
                        "current_heading": heading,
                        "content_belongs_to": "",
                        "surrounding_text": surrounding[:200],
                        "text_preview": surrounding[:120],
                        "verdict": "irrelevant",
                        "similarity": rel["similarity"],
                        "confidence": conf_pct,
                        "relevant": False,
                        "_replace_image": True,
                    })
            except Exception as exc:
                print(f"[image_analysis] error on {img.image_id}: {exc}")
        return issues

    return await asyncio.to_thread(_process_all)


async def recheck_image(
    client: Any = None,
    b64: str = "",
    surrounding_text: str = "",
    image_id: str = "",
) -> Dict[str, Any]:
    """Run local ethics + relevance on a single replacement image (one pass)."""
    from functions.image_ethics import analyze_image_ethics_sync

    def _both() -> Dict[str, Any]:
        ethics_raw = analyze_image_ethics_sync(b64)
        relevance_raw = analyze_image_relevance_sync(
            b64,
            heading="",
            paragraph=surrounding_text or "",
            caption=ethics_raw.get("caption") or "",
            skip_caption=True,
        )
        return ethics_raw, relevance_raw

    ethics_raw, relevance_raw = await asyncio.to_thread(_both)
    ethics = {
        "verdict": ethics_raw["verdict"],
        "is_ethical": ethics_raw["ethical"],
        "ethical": ethics_raw["ethical"],
        "category": ethics_raw["category"],
        "confidence": ethics_raw["confidence"],
        "reason": ethics_raw["reason"],
        "caption": ethics_raw.get("caption", ""),
    }
    relevance = {
        "verdict": relevance_raw["verdict"],
        "is_relevant": relevance_raw["relevant"],
        "relevant": relevance_raw["relevant"],
        "similarity": relevance_raw["similarity"],
        "confidence": float(relevance_raw["similarity"]),
        "reason": relevance_raw["reason"],
        "caption": relevance_raw.get("caption", ""),
    }
    cleared = bool(ethics.get("is_ethical")) and bool(relevance.get("is_relevant"))
    print(
        f"[recheck_image] image_id={image_id} | "
        f"ethical={ethics['ethical']} ({ethics['category']}) | "
        f"relevant={relevance['relevant']} (sim={relevance['similarity']}) | "
        f"cleared={cleared}"
    )
    return {
        "image_id": image_id,
        "ethics": ethics,
        "relevance": relevance,
        "cleared": cleared,
        "is_relevant": relevance.get("is_relevant", False),
        "is_ethical": ethics.get("is_ethical", True),
        "confidence": relevance.get("confidence", 0),
        "similarity": relevance.get("similarity", 0),
    }
