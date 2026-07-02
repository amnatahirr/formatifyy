"""
batcher.py — Batching layer for Formatify.

Groups document pages into batches of 4 with 1-page overlap. The overlap pages
are marked as context-only so they never generate duplicate issues downstream.
"""

from __future__ import annotations

from typing import List

from models import DocumentModel, ParagraphBlock, ImageBlock, Batch


def create_batches(doc: DocumentModel, batch_size: int = 4, overlap: int = 1) -> List[Batch]:
    """
    Split the document into page-based batches.

    Parameters
    ----------
    doc : DocumentModel
        The parsed document.
    batch_size : int
        Number of pages per batch (default 4).
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

    batches: List[Batch] = []
    batch_index = 0
    page_start = 1

    while page_start <= doc.total_pages:
        page_end = min(page_start + batch_size - 1, doc.total_pages)

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

    return batches
