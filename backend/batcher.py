"""
batcher.py — Batching layer for Formatify.

Groups document pages into dynamic batches based on document length and
content density, with 1-page overlap as context-only so overlap pages never
generate duplicate issues downstream.

Rules (pages + density, with min/max):
  - Small  (<=8 pages):  1 batch (whole document)
  - Medium (9–25):       ~4–6 pages / batch
  - Large  (25+):        ~6–8 pages / batch
  - Dense pages:         fewer pages / batch (within the range)
  - Light pages:         more pages / batch (within the range)

Goal: each batch carries roughly the same text volume so Claude calls stay
balanced and parallel batches remain effective.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from models import DocumentModel, ParagraphBlock, ImageBlock, Batch

logger = logging.getLogger(__name__)

# Content-density thresholds (average body characters per page).
# Tuned for academic docs: ~250–500 words ≈ 1500–3000 chars/page is typical.
_DENSE_CHARS_PER_PAGE = 3200
_LIGHT_CHARS_PER_PAGE = 1100


def _chars_by_page(doc: DocumentModel) -> Dict[int, int]:
    """Return character counts keyed by page number (1-indexed)."""
    counts: Dict[int, int] = {pg: 0 for pg in range(1, doc.total_pages + 1)}
    for p in doc.paragraphs:
        pg = p.page_number
        if pg in counts:
            counts[pg] += len(p.text or "")
    return counts


def _average_chars_per_page(chars_by_page: Dict[int, int]) -> float:
    """
    Mean chars/page. Prefer pages that actually have text so sparse / mis-mapped
    page numbers (e.g. some PDF extractions) do not collapse density to near-zero.
    Falls back to all pages when every page is empty.
    """
    if not chars_by_page:
        return 0.0
    nonempty = [c for c in chars_by_page.values() if c > 0]
    values = nonempty if nonempty else list(chars_by_page.values())
    return sum(values) / len(values)


def _density_label(avg_chars: float) -> str:
    if avg_chars >= _DENSE_CHARS_PER_PAGE:
        return "dense"
    if avg_chars <= _LIGHT_CHARS_PER_PAGE:
        return "light"
    return "normal"


def resolve_batch_limits(
    total_pages: int,
    avg_chars_per_page: float,
) -> Tuple[int, int, int, int]:
    """
    Decide min/max/target pages-per-batch and target chars-per-batch.

    Returns
    -------
    (min_pages, max_pages, target_pages, target_chars)
    """
    if total_pages <= 0:
        return (1, 1, 1, 0)

    # Small docs: single batch covering the whole document.
    if total_pages <= 8:
        total_chars = int(round(avg_chars_per_page * total_pages))
        return (total_pages, total_pages, total_pages, total_chars)

    if total_pages <= 25:
        min_pages, max_pages, default_pages = 4, 6, 5
    else:
        min_pages, max_pages, default_pages = 6, 8, 7

    density = _density_label(avg_chars_per_page)
    if density == "dense":
        target_pages = min_pages
    elif density == "light":
        target_pages = max_pages
    else:
        target_pages = default_pages

    # Volume target so dense/light pages pack to similar Claude payload sizes.
    target_chars = int(round(avg_chars_per_page * target_pages))
    # Floor so extremely light docs still form sensible batches.
    if target_chars <= 0:
        target_chars = target_pages * max(1, int(avg_chars_per_page) or 1500)

    return (min_pages, max_pages, target_pages, target_chars)


def _pick_page_end(
    page_start: int,
    total_pages: int,
    chars_by_page: Dict[int, int],
    min_pages: int,
    max_pages: int,
    target_pages: int,
    target_chars: int,
) -> int:
    """
    Grow a batch from page_start until volume/page limits say stop.

    Stop when any of:
      - reached end of document
      - hit max_pages
      - reached target_pages and have ~target text volume
      - already at/above min_pages and text volume hits the target
    """
    if min_pages == max_pages == total_pages and page_start == 1:
        return total_pages

    page_end = page_start
    running_chars = 0
    pages_taken = 0

    while page_end <= total_pages:
        running_chars += chars_by_page.get(page_end, 0)
        pages_taken += 1

        at_doc_end = page_end >= total_pages
        at_max = pages_taken >= max_pages
        hit_target_pages = pages_taken >= target_pages
        hit_volume = running_chars >= target_chars
        past_min = pages_taken >= min_pages

        if at_doc_end or at_max:
            break
        # Prefer closing near the suggested page count once volume is close.
        if hit_target_pages and running_chars >= int(target_chars * 0.85):
            break
        # Dense stretch: stop early (but not below min) once volume is full.
        if past_min and hit_volume:
            break

        page_end += 1

    return page_end


def create_batches(
    doc: DocumentModel,
    batch_size: Optional[int] = None,
    overlap: int = 1,
) -> List[Batch]:
    """
    Split the document into page-based batches.

    Parameters
    ----------
    doc : DocumentModel
        The parsed document.
    batch_size : int, optional
        If provided, use a fixed page count (legacy override).
        If omitted/None, size is chosen dynamically from length + density.
    overlap : int
        Number of pages carried over from the previous batch as context-only
        (default 1).

    Returns
    -------
    List[Batch]
        Ordered list of batches ready for the dispatcher.
    """
    if doc.total_pages == 0:
        return []

    # Pre-index paragraphs and images by page number
    paras_by_page: dict[int, List[ParagraphBlock]] = {}
    imgs_by_page: dict[int, List[ImageBlock]] = {}

    for p in doc.paragraphs:
        paras_by_page.setdefault(p.page_number, []).append(p)
    for img in doc.images:
        imgs_by_page.setdefault(img.page_number, []).append(img)

    chars_by_page = _chars_by_page(doc)
    avg_chars = _average_chars_per_page(chars_by_page)
    density = _density_label(avg_chars)

    if batch_size is not None:
        # Legacy / explicit override: fixed page steps.
        min_pages = max_pages = target_pages = max(1, batch_size)
        target_chars = int(round(avg_chars * target_pages))
        dynamic = False
    else:
        min_pages, max_pages, target_pages, target_chars = resolve_batch_limits(
            doc.total_pages, avg_chars
        )
        dynamic = True

    batches: List[Batch] = []
    batch_index = 0
    page_start = 1

    while page_start <= doc.total_pages:
        if batch_size is not None:
            page_end = min(page_start + batch_size - 1, doc.total_pages)
        else:
            page_end = _pick_page_end(
                page_start=page_start,
                total_pages=doc.total_pages,
                chars_by_page=chars_by_page,
                min_pages=min_pages,
                max_pages=max_pages,
                target_pages=target_pages,
                target_chars=target_chars,
            )

        # Collect primary paragraphs and images for this batch
        batch_paras: List[ParagraphBlock] = []
        batch_imgs: List[ImageBlock] = []
        for pg in range(page_start, page_end + 1):
            batch_paras.extend(paras_by_page.get(pg, []))
            batch_imgs.extend(imgs_by_page.get(pg, []))

        # Collect context paragraphs from the overlap window of the
        # PREVIOUS batch (the last `overlap` pages before page_start).
        context_paras: List[ParagraphBlock] = []
        if page_start > 1:
            ctx_start = max(1, page_start - overlap)
            for pg in range(ctx_start, page_start):
                context_paras.extend(paras_by_page.get(pg, []))

        batches.append(
            Batch(
                batch_index=batch_index,
                page_start=page_start,
                page_end=page_end,
                paragraphs=batch_paras,
                images=batch_imgs,
                context_paragraphs=context_paras,
            )
        )

        batch_index += 1
        page_start = page_end + 1  # next batch starts right after

    # Rebalance a tiny leftover against the previous batch so Claude isn't
    # called for a 1–2 page stub. Merge when combined size fits near max;
    # otherwise split the combined range as evenly as possible.
    if (
        batch_size is None
        and len(batches) >= 2
        and min_pages < doc.total_pages
    ):
        last = batches[-1]
        last_len = last.page_end - last.page_start + 1
        if last_len < min_pages:
            prev = batches[-2]

            def _rebuild(page_start: int, page_end: int, batch_index: int) -> Batch:
                paras: List[ParagraphBlock] = []
                imgs: List[ImageBlock] = []
                for pg in range(page_start, page_end + 1):
                    paras.extend(paras_by_page.get(pg, []))
                    imgs.extend(imgs_by_page.get(pg, []))
                ctx: List[ParagraphBlock] = []
                if page_start > 1:
                    ctx_start = max(1, page_start - overlap)
                    for pg in range(ctx_start, page_start):
                        ctx.extend(paras_by_page.get(pg, []))
                return Batch(
                    batch_index=batch_index,
                    page_start=page_start,
                    page_end=page_end,
                    paragraphs=paras,
                    images=imgs,
                    context_paragraphs=ctx,
                )

            combined_start = prev.page_start
            combined_end = last.page_end
            combined_len = combined_end - combined_start + 1
            # Light/normal docs can absorb a slightly larger final batch;
            # dense docs prefer an even split to avoid oversized Claude payloads.
            merge_cap = max_pages + (1 if density == "dense" else 2)

            if combined_len <= merge_cap:
                batches[-2] = _rebuild(combined_start, combined_end, prev.batch_index)
                batches.pop()
                for i, b in enumerate(batches):
                    if b.batch_index != i:
                        batches[i] = b.model_copy(update={"batch_index": i})
            else:
                # Even split, keeping each side within max_pages when possible.
                first_len = min(max_pages, combined_len // 2)
                first_len = max(first_len, combined_len - max_pages)
                mid_end = combined_start + first_len - 1
                batches[-2] = _rebuild(combined_start, mid_end, prev.batch_index)
                batches[-1] = _rebuild(mid_end + 1, combined_end, last.batch_index)

    ranges = [f"{b.page_start}-{b.page_end}" for b in batches]
    mode = "dynamic" if dynamic else f"fixed({batch_size})"
    logger.info(
        "[batcher] %s | pages=%d avg_chars/page=%.0f density=%s "
        "limits=%d-%d target_pages=%d target_chars=%d -> %d batches %s",
        mode,
        doc.total_pages,
        avg_chars,
        density,
        min_pages,
        max_pages,
        target_pages,
        target_chars,
        len(batches),
        ranges,
    )
    # Also print so it shows up even when logging is not configured.
    print(
        f"[batcher] {mode} pages={doc.total_pages} density={density} "
        f"avg_chars/page={avg_chars:.0f} limits={min_pages}-{max_pages} "
        f"-> {len(batches)} batches {ranges}"
    )

    return batches
