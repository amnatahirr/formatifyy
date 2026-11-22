"""
dispatcher.py — Parallel dispatcher for Formatify.

Uses asyncio.gather to fire all analysis functions for every batch
concurrently (grammar runs once per document, locally). A single failed function never stops the pipeline thanks to
return_exceptions=True.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Union

import anthropic

from models import Batch
from functions.grammar import check_grammar
from functions.formatting import check_formatting
from functions.formatting_freeform import check_formatting_freeform
from functions.image_relevance import check_images_combined
from functions.para_relevance import check_para_relevance
from functions.plagiarism import check_plagiarism, llm_pattern_plagiarism_enabled


async def dispatch_all(
    client: anthropic.AsyncAnthropic,
    batches: List[Batch],
    template: Union[str, Dict[str, Any]],
    outline: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Run all analysis functions across all batches in parallel.

    `outline` is the document-level heading outline (functions/outline.py); it is
    passed to formatting so heading levels are never re-decided per batch.

    Image ethics + relevance share a single local vision pass per batch
    (one BLIP caption + one CLIP score per image).

    Corpus plagiarism runs once at document level in main._run_analysis
    (not per batch). Optional LLM pattern plagiarism can still run here when
    PLAGIARISM_LLM_PATTERNS=true.
    """
    tasks: List[asyncio.Task] = []
    run_llm_plagiarism = llm_pattern_plagiarism_enabled()

    # Local grammar model: one call for the whole report (better batching,
    # one timing log per report) instead of one call per batch.
    tasks.append(asyncio.ensure_future(
        _safe_call(check_grammar, client, _whole_document_batch(batches))
    ))
    for batch in batches:
        tasks.append(asyncio.ensure_future(
            _safe_call_formatting(check_formatting, client, batch, template, outline)
        ))
        # Combined local image ethics + relevance (faster than two separate passes)
        tasks.append(asyncio.ensure_future(
            _safe_call(check_images_combined, client, batch)
        ))
        tasks.append(asyncio.ensure_future(
            _safe_call(check_para_relevance, client, batch)
        ))
        if run_llm_plagiarism:
            tasks.append(asyncio.ensure_future(
                _safe_call(check_plagiarism, client, batch)
            ))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_issues: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            print(f"[dispatcher] function raised: {result}")
            continue
        if isinstance(result, list):
            all_issues.extend(result)

    return all_issues


async def dispatch_freeform(
    client: anthropic.AsyncAnthropic,
    batches: List[Batch],
) -> List[Dict[str, Any]]:
    """
    Template-free analysis path.

    Runs: freeform formatting + grammar + images + para_relevance.
    Does NOT run template formatting, section-order/missing-section, or
    LLM plagiarism-pattern checks (corpus plagiarism is handled in main).
    """
    tasks: List[asyncio.Task] = []
    tasks.append(asyncio.ensure_future(
        _safe_call(check_grammar, client, _whole_document_batch(batches))
    ))
    for batch in batches:
        tasks.append(
            asyncio.ensure_future(_safe_call(check_formatting_freeform, client, batch))
        )
        tasks.append(
            asyncio.ensure_future(_safe_call(check_images_combined, client, batch))
        )
        tasks.append(
            asyncio.ensure_future(_safe_call(check_para_relevance, client, batch))
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_issues: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            print(f"[dispatcher] freeform function raised: {result}")
            continue
        if isinstance(result, list):
            all_issues.extend(result)
    return all_issues


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _whole_document_batch(batches: List[Batch]) -> Batch:
    """All paragraphs of the report in one Batch (deduplicated by paragraph_id)."""
    seen = set()
    paragraphs = []
    for b in batches:
        for p in b.paragraphs:
            if p.paragraph_id in seen:
                continue
            seen.add(p.paragraph_id)
            paragraphs.append(p)
    return Batch(
        batch_index=0,
        page_start=min((b.page_start for b in batches), default=0),
        page_end=max((b.page_end for b in batches), default=0),
        paragraphs=paragraphs,
    )


async def _safe_call(fn, client, batch) -> List[Dict[str, Any]]:
    """Wrap a function call so individual failures return [] instead of raising."""
    try:
        return await fn(client, batch)
    except Exception as exc:
        print(f"[dispatcher] {fn.__module__} failed: {exc}")
        return []


async def _safe_call_formatting(fn, client, batch, template, outline=None) -> List[Dict[str, Any]]:
    """Formatting takes the full template dict plus the resolved heading outline."""
    try:
        return await fn(client, batch, template, outline=outline)
    except Exception as exc:
        print(f"[dispatcher] formatting failed: {exc}")
        return []