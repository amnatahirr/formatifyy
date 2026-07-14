"""
dispatcher.py — Parallel dispatcher for Formatify.

Uses asyncio.gather to fire all 6 analysis functions for every batch
concurrently. A single failed function never stops the pipeline thanks to
return_exceptions=True.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Union

import anthropic

from models import Batch
from functions.grammar import check_grammar
from functions.formatting import check_formatting
from functions.image_relevance import check_images_combined
from functions.para_relevance import check_para_relevance
from functions.plagiarism import check_plagiarism


async def dispatch_all(
    client: anthropic.AsyncAnthropic,
    batches: List[Batch],
    template: Union[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Run all analysis functions across all batches in parallel.

    Image ethics + relevance share a single local vision pass per batch
    (one BLIP caption + one CLIP score per image).
    """
    tasks: List[asyncio.Task] = []

    for batch in batches:
        tasks.append(asyncio.ensure_future(
            _safe_call(check_grammar, client, batch)
        ))
        tasks.append(asyncio.ensure_future(
            _safe_call_formatting(check_formatting, client, batch, template)
        ))
        # Combined local image ethics + relevance (faster than two separate passes)
        tasks.append(asyncio.ensure_future(
            _safe_call(check_images_combined, client, batch)
        ))
        tasks.append(asyncio.ensure_future(
            _safe_call(check_para_relevance, client, batch)
        ))
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _safe_call(fn, client, batch) -> List[Dict[str, Any]]:
    """Wrap a function call so individual failures return [] instead of raising."""
    try:
        return await fn(client, batch)
    except Exception as exc:
        print(f"[dispatcher] {fn.__module__} failed: {exc}")
        return []


async def _safe_call_formatting(fn, client, batch, template) -> List[Dict[str, Any]]:
    """Formatting function has an extra parameter (the full template dict)."""
    try:
        return await fn(client, batch, template)
    except Exception as exc:
        print(f"[dispatcher] formatting failed: {exc}")
        return []