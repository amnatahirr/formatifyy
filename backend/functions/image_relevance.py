"""
functions/image_relevance.py — Local image–section relevance detector.

Compares each image to the text immediately BEFORE and AFTER it in the
document (plus nearest heading), using CLIP + BLIP caption signals.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

from models import Batch, ImageBlock, ParagraphBlock
from functions.local_vision import (
    clip_similarity_from_b64,
    generate_caption_from_b64,
    image_fingerprint,
    is_diagram_like_from_b64,
)


# CLIP image↔text cosine for mismatched pairs is typically ~0.12–0.20;
# on-topic academic figures usually land ~0.24+. Decision uses IMAGE↔text
# only — CLIP text↔text (caption vs context) scores ~0.5 even for unrelated
# English and must NOT be blended into the relevance score.
DEFAULT_RELEVANCE_THRESHOLD = 0.22
_KEYWORD_BONUS_MAX = 0.03
_BEFORE_PARAS = 4
_AFTER_PARAS = 4

_CAPTION_LIKE_RE = re.compile(
    r"^(figure|fig\.?|image|table|chart|diagram)\b",
    re.IGNORECASE,
)


_DIAGRAM_KEYWORDS_RE = re.compile(
    r"\b(use[\s-]?case|actors?|uml|erd|entity[\s-]relationship|dfd|data[\s-]flow|"
    r"sequence|class[\s-]diagram|activity[\s-]diagram|state[\s-](?:chart|machine|diagram)|"
    r"flow[\s-]?chart|architecture|block[\s-]diagram|deployment|component[\s-]diagram|"
    r"context[\s-]diagram|schema)\b",
    re.IGNORECASE,
)


def nearby_caption_text(
    batch: Batch, img: ImageBlock, *, before_n: int = 2, after_n: int = 3
) -> str:
    """Figure caption(s) right next to the image, e.g. 'Figure 3.2: Use Case Diagram'."""
    img_num = _para_num((img.paragraph_id or "").strip())
    if img_num is None:
        return ""
    parts: List[str] = []
    for p in _ordered_paragraphs(batch):
        pn = _para_num(p.paragraph_id)
        if pn is None or not (img_num - before_n <= pn <= img_num + after_n):
            continue
        t = (p.text or "").strip()
        if t and _CAPTION_LIKE_RE.match(t) and len(t.split()) <= 30:
            parts.append(t)
    return " ".join(parts)


def _diagram_relevant_result(reason, threshold, caption, heading, before_text, after_text):
    return {
        "similarity": 1.0,
        "clip_similarity": 0.0,
        "caption_alignment": 0.0,
        "relevant": True,
        "is_relevant": True,
        "verdict": "relevant",
        "confidence": 1.0,
        "threshold": threshold,
        "caption": caption or "",
        "heading": heading,
        "before_text": before_text,
        "after_text": after_text,
        "keyword_matches": [],
        "reason": reason,
    }


def _build_section_text(heading: str, before: str, after: str) -> str:
    parts = [
        p.strip()
        for p in (heading or "", before or "", after or "")
        if p and p.strip()
    ]
    return " ".join(parts).strip()


def _extract_keywords(text: str) -> set:
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "are", "was", "has",
        "have", "its", "into", "also", "below", "above", "following", "shows",
        "shown", "figure", "image", "diagram", "each", "used", "uses", "using",
        "based", "which", "their", "they", "them", "then", "than", "when",
        "where", "how", "all", "any", "can", "may", "will", "two", "one",
        "data", "system", "process", "result", "results", "report", "chapter",
        "section", "page", "content", "text", "document",
    }
    words = set(re.findall(r"\b[a-zA-Z]{4,}\b", (text or "").lower()))
    return words - stop


def _para_num(paragraph_id: str | None) -> Optional[int]:
    m = re.match(r"p(\d+)", paragraph_id or "")
    return int(m.group(1)) if m else None


def _para_sort_key(p: ParagraphBlock) -> Tuple[int, str]:
    n = _para_num(p.paragraph_id)
    return (n if n is not None else 10**9, p.paragraph_id or "")


def _is_caption_para(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _CAPTION_LIKE_RE.match(t) and len(t.split()) <= 30:
        return True
    return False


def _ordered_paragraphs(batch: Batch) -> List[ParagraphBlock]:
    seen: set[str] = set()
    out: List[ParagraphBlock] = []
    for p in list(batch.context_paragraphs) + list(batch.paragraphs):
        pid = p.paragraph_id or ""
        if pid in seen:
            continue
        seen.add(pid)
        out.append(p)
    out.sort(key=_para_sort_key)
    return out


def surrounding_context_for_image(
    batch: Batch,
    img: ImageBlock,
    *,
    before_n: int = _BEFORE_PARAS,
    after_n: int = _AFTER_PARAS,
) -> Dict[str, str]:
    """
    Collect heading + text immediately before/after the image's anchor paragraph.

    DOCX image-only paragraphs often have empty text and are omitted from the
    paragraph list, while the image still keeps paragraph_id=pN. In that case
    we split by paragraph number so each image gets its own local context
    (not the same mid-page fallback for every image on the page).
    """
    paras = _ordered_paragraphs(batch)
    if not paras:
        return {
            "heading": "",
            "before": "",
            "after": "",
            "section_text": "",
        }

    anchor_id = (img.paragraph_id or "").strip()
    img_num = _para_num(anchor_id)
    anchor_idx: Optional[int] = None

    if anchor_id:
        for i, p in enumerate(paras):
            if p.paragraph_id == anchor_id:
                anchor_idx = i
                break

    # Exact pid missing (typical for empty image-only DOCX paras): split by index.
    if anchor_idx is None and img_num is not None:
        before_pool: List[ParagraphBlock] = []
        after_pool: List[ParagraphBlock] = []
        for p in paras:
            pn = _para_num(p.paragraph_id)
            if pn is None:
                continue
            if pn < img_num:
                before_pool.append(p)
            elif pn > img_num:
                after_pool.append(p)
            elif (p.text or "").strip():
                after_pool.insert(0, p)

        heading = ""
        for p in reversed(before_pool):
            if (p.heading_context or "").strip():
                heading = p.heading_context.strip()
                break
            if (p.style or "").lower().startswith("heading") and (p.text or "").strip():
                heading = (p.text or "").strip()
                break

        before_parts: List[str] = []
        for p in reversed(before_pool):
            t = (p.text or "").strip()
            if not t or _is_caption_para(t):
                continue
            if (p.style or "").lower().startswith("heading") and before_parts:
                if not heading:
                    heading = t
                break
            before_parts.insert(0, t)
            if len(before_parts) >= before_n:
                break

        after_parts: List[str] = []
        for p in after_pool:
            t = (p.text or "").strip()
            if not t or _is_caption_para(t):
                continue
            if (p.style or "").lower().startswith("heading") and after_parts:
                break
            after_parts.append(t)
            if len(after_parts) >= after_n:
                break

        before = " ".join(before_parts)
        after = " ".join(after_parts)
        section = _build_section_text(heading, before, after)
        return {
            "heading": heading,
            "before": before,
            "after": after,
            "section_text": section,
        }

    # Fallback without any paragraph id: same-page mid split (last resort).
    if anchor_idx is None:
        same_page = [p for p in paras if p.page_number == img.page_number]
        pool = same_page or paras
        mid = max(1, len(pool) // 2)
        before_pool = pool[:mid]
        after_pool = pool[mid:]
        heading = ""
        for p in reversed(before_pool):
            if (p.heading_context or "").strip():
                heading = p.heading_context.strip()
                break
            if (p.style or "").lower().startswith("heading"):
                heading = (p.text or "").strip()
                break
        before = " ".join(
            (p.text or "").strip()
            for p in before_pool[-before_n:]
            if (p.text or "").strip() and not _is_caption_para(p.text or "")
        )
        after = " ".join(
            (p.text or "").strip()
            for p in after_pool[:after_n]
            if (p.text or "").strip() and not _is_caption_para(p.text or "")
        )
        section = _build_section_text(heading, before, after)
        return {
            "heading": heading,
            "before": before,
            "after": after,
            "section_text": section,
        }

    # Exact anchor found — walk neighbors.
    heading = ""
    before_parts: List[str] = []
    for j in range(anchor_idx - 1, -1, -1):
        p = paras[j]
        if not heading and (p.heading_context or "").strip():
            heading = p.heading_context.strip()
        if not heading and (p.style or "").lower().startswith("heading"):
            heading = (p.text or "").strip()
        t = (p.text or "").strip()
        if not t or _is_caption_para(t):
            continue
        if (p.style or "").lower().startswith("heading") and before_parts:
            if not heading:
                heading = t
            break
        before_parts.insert(0, t)
        if len(before_parts) >= before_n:
            break

    after_parts: List[str] = []
    for j in range(anchor_idx + 1, len(paras)):
        p = paras[j]
        t = (p.text or "").strip()
        if not t:
            continue
        if _is_caption_para(t):
            continue
        if (p.style or "").lower().startswith("heading") and after_parts:
            break
        after_parts.append(t)
        if len(after_parts) >= after_n:
            break

    if not heading:
        heading = (paras[anchor_idx].heading_context or "").strip()

    before = " ".join(before_parts)
    after = " ".join(after_parts)
    section = _build_section_text(heading, before, after)
    return {
        "heading": heading,
        "before": before,
        "after": after,
        "section_text": section,
    }



def analyze_image_relevance_sync(
    b64: str,
    heading: str = "",
    paragraph: str = "",
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    caption: str | None = None,
    skip_caption: bool = False,
    before_text: str = "",
    after_text: str = "",
    figure_caption: str = "",
) -> dict:
    """
    Local CLIP relevance analysis against surrounding section text.

    Prefer before_text/after_text when provided; `paragraph` is treated as a
    combined surrounding blob for backward compatibility.
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
            "before_text": before_text,
            "after_text": after_text,
        }

    # Diagrams (use case, class, ER, DFD, flowcharts...) cannot be judged by
    # CLIP — treat them as relevant instead of flagging them falsely.
        # 1) Figure caption explicitly says it's a diagram (strongest signal).
    if figure_caption and _DIAGRAM_KEYWORDS_RE.search(figure_caption):
        print(f"[image_relevance] RELEVANT | diagram caption: '{figure_caption[:60]}'")
        return _diagram_relevant_result(
            f"Figure caption identifies a technical diagram: '{figure_caption[:80]}'.",
            threshold, caption, heading, before_text, after_text,
        )

    # 2) Image itself looks like a diagram (UML/flowchart/architecture...).
    if is_diagram_like_from_b64(b64):
        print("[image_relevance] RELEVANT | diagram-like image, CLIP skipped")
        return _diagram_relevant_result(
            "Diagram-style image (UML/flowchart/architecture); "
            "photo-based CLIP scoring is not applicable.",
            threshold, caption, heading, before_text, after_text,
        )

    if before_text or after_text:
        section_text = _build_section_text(heading, before_text, after_text)
    else:
        section_text = _build_section_text(heading, paragraph, "")

    if not section_text:
        # No usable context — cannot claim relevance.
        return {
            "similarity": 0.0,
            "relevant": False,
            "is_relevant": False,
            "verdict": "irrelevant",
            "confidence": 0.85,
            "reason": "No surrounding text found before/after the image to assess relevance.",
            "caption": caption or "",
            "before_text": before_text,
            "after_text": after_text,
            "heading": heading,
            "threshold": threshold,
        }

    # Truncate for CLIP (text encoder limit)
    clip_text = section_text[:500]
    similarity = clip_similarity_from_b64(b64, clip_text)

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
            keyword_bonus = min(_KEYWORD_BONUS_MAX, 0.015 * len(matches))

    # Primary signal is image↔context CLIP. Caption keywords may add a tiny
    # bonus only; CLIP caption↔text is intentionally unused (too noisy).
    final_score = min(1.0, similarity + keyword_bonus)
    relevant = final_score >= threshold

    # Hard guard: clearly mismatched visuals stay irrelevant even with bonus.
    if similarity < (threshold - 0.03):
        relevant = False
        final_score = similarity

    reason_parts = [
        f"CLIP(image↔context)={similarity:.3f}",
    ]
    if matches:
        reason_parts.append(f"keyword_bonus={keyword_bonus:.3f} matches={matches}")
    reason_parts.append(f"score={final_score:.3f} vs threshold={threshold:.2f}")
    if caption:
        reason_parts.append(f"Caption: '{caption}'")
    if before_text:
        reason_parts.append(f"Before: '{before_text[:100]}'")
    if after_text:
        reason_parts.append(f"After: '{after_text[:100]}'")
    reason = ". ".join(reason_parts) + "."

    tag = "RELEVANT" if relevant else "IRRELEVANT"
    print(
        f"[image_relevance] {tag} | score={final_score:.3f} | "
        f"img_clip={similarity:.3f} | "
        f"heading='{(heading or '')[:50]}' | "
        f"before='{(before_text or '')[:40]}' | after='{(after_text or '')[:40]}' | "
        f"caption='{(caption or '')[:60]}'"
    )

    return {
        "similarity": round(final_score, 4),
        "clip_similarity": round(similarity, 4),
        "caption_alignment": 0.0,
        "relevant": relevant,
        "is_relevant": relevant,
        "verdict": "relevant" if relevant else "irrelevant",
        "confidence": round(1.0 - final_score if not relevant else final_score, 4),
        "threshold": threshold,
        "caption": caption,
        "heading": heading,
        "before_text": before_text,
        "after_text": after_text,
        "keyword_matches": matches,
        "reason": reason,
    }


def _surrounding_for_image(batch: Batch, page_number: int) -> tuple[str, str]:
    """Legacy helper kept for callers that only pass page_number."""
    dummy = ImageBlock(image_id="", page_number=page_number, base64="")
    ctx = surrounding_context_for_image(batch, dummy)
    return ctx["heading"], ctx["section_text"]


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


def _issue_from_relevance(
    image_id: str,
    page: int,
    heading: str,
    before: str,
    after: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    conf = float(result.get("similarity") or 0)
    # Confidence for UI: how confident we are it is IRRELEVANT
    irr_conf = max(0.0, min(1.0, 1.0 - conf))
    conf_pct = int(round(irr_conf * 100))
    surrounding = _build_section_text(heading, before, after)

    return {
        "function": "image_relevance",
        "type": "image_relevance",
        "severity": "major",
        "paragraph_id": "",
        "image_id": image_id,
        "page": page,
        "reason": result["reason"],
        "suggestion": "Replace this image with one that matches the surrounding content "
        "(text before and after the figure).",
        "explanation": result["reason"],
        "original": "",
        "current_heading": heading,
        "content_belongs_to": "",
        "surrounding_text": surrounding[:400],
        "text_before": (before or "")[:200],
        "text_after": (after or "")[:200],
        "text_preview": surrounding[:120],
        "verdict": "irrelevant",
        "similarity": result["similarity"],
        "confidence": conf_pct,
        "relevant": False,
        "_replace_image": True,
    }


async def _evaluate_relevance(
    image_id: str,
    page: int,
    b64: str,
    heading: str,
    paragraph: str,
    caption: str | None = None,
    before_text: str = "",
    after_text: str = "",
    figure_caption: str = "",
) -> Optional[Dict[str, Any]]:
    result = await asyncio.to_thread(
        lambda: analyze_image_relevance_sync(
            b64,
            heading=heading,
            paragraph=paragraph,
            caption=caption,
            skip_caption=False,
            before_text=before_text,
            after_text=after_text,
            figure_caption=figure_caption,
        )
    )
    if result["relevant"]:
        return None
    return _issue_from_relevance(
        image_id,
        page,
        heading,
        before_text or "",
        after_text or "",
        result,
    )


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
        ctx = surrounding_context_for_image(batch, img)
        try:
            issue = await _evaluate_relevance(
                img.image_id,
                img.page_number,
                img.base64,
                ctx["heading"],
                ctx["section_text"],
                before_text=ctx["before"],
                after_text=ctx["after"],
                figure_caption=ctx.get("figure_caption") or nearby_caption_text(batch, img),
            )
            if issue:
                results.append(issue)
        except Exception as exc:
            print(f"[image_relevance] error on {img.image_id}: {exc}")
            continue
    return results


async def check_images_combined(
    client: Any,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    Single pass over batch images: one BLIP caption + CLIP relevance vs
    before/after text, plus ethics.
    """
    from functions.image_ethics import analyze_image_ethics_sync

    if not batch.images:
        return []

    def _process_all() -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        for img in batch.images:
            if not img.base64:
                continue
            ctx = surrounding_context_for_image(batch, img)
            heading = ctx["heading"]
            before = ctx["before"]
            after = ctx["after"]
            section = ctx["section_text"]
            caption = ""
            try:
                ethics = analyze_image_ethics_sync(img.base64)
                caption = ethics.get("caption") or ""
                if not ethics["ethical"]:
                    conf = ethics["confidence"]
                    conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(conf)
                    issues.append({
                        "function": "image_ethics",
                        "type": "image_ethics",
                        "severity": "major",
                        "paragraph_id": img.paragraph_id or "",
                        "image_id": img.image_id,
                        "page": img.page_number,
                        "reason": ethics["reason"],
                        "suggestion": "Replace this image with appropriate academic content.",
                        "explanation": ethics["reason"],
                        "debug_reason": ethics.get("debug_reason", ""),
                        "original": "",
                        "current_heading": heading,
                        "content_belongs_to": "",
                        "text_preview": caption[:120],
                        "verdict": "unethical",
                        "ethics_category": ethics["category"],
                        "confidence": conf_pct,
                        "ethical": False,
                        "_replace_image": True,
                    })
            except Exception as exc:
                print(f"[image_ethics] error on {img.image_id}: {exc}")

            try:
                rel = analyze_image_relevance_sync(
                    img.base64,
                    heading=heading,
                    paragraph=section,
                    caption=caption,
                    skip_caption=bool(caption),
                    before_text=before,
                    after_text=after,
                    figure_caption=nearby_caption_text(batch, img),
                )
                if not rel["relevant"]:
                    issues.append(
                        _issue_from_relevance(
                            img.image_id,
                            img.page_number,
                            heading,
                            before,
                            after,
                            rel,
                        )
                    )
            except Exception as exc:
                print(f"[image_relevance] error on {img.image_id}: {exc}")
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

    def _both() -> tuple:
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
