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
from functions.image_ethics import check_image_ethics
from functions.image_relevance import check_image_relevance
from functions.para_relevance import check_para_relevance
from functions.plagiarism import check_plagiarism


async def dispatch_all(
    client: anthropic.AsyncAnthropic,
    batches: List[Batch],
    template: Union[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Run all 6 analysis functions across all batches in parallel.

    Parameters
    ----------
    client : AsyncAnthropic
        The shared Anthropic async client.
    batches : list[Batch]
        Batches produced by the batcher.
    template : dict | str
        The FULL structured template dict as returned by
        templates.get_template_by_id() / get_all_templates()
        (i.e. containing required_sections + formatting_rules +
        markdown_rules). Passing the full dict — not just
        template["markdown_rules"] — is required for check_formatting
        to build explicit per-heading-level rules (Heading 1, 2, 3...).
        A plain markdown string is still accepted for backward
        compatibility, but per-level heading detection will be weaker.

    Returns
    -------
    list[dict]
        Flat list of raw issue dicts from every function × every batch.
    """
    # Build one coroutine per (batch × function) combination
    tasks: List[asyncio.Task] = []

    for batch in batches:
        # 1. Grammar
        tasks.append(asyncio.ensure_future(
            _safe_call(check_grammar, client, batch)
        ))
        # 2. Formatting
        tasks.append(asyncio.ensure_future(
            _safe_call_formatting(check_formatting, client, batch, template)
        ))
        # 3. Image Ethics
        tasks.append(asyncio.ensure_future(
            _safe_call(check_image_ethics, client, batch)
        ))
        # 4. Image Relevance
        tasks.append(asyncio.ensure_future(
            _safe_call(check_image_relevance, client, batch)
        ))
        # 5. Paragraph Relevance
        tasks.append(asyncio.ensure_future(
            _safe_call(check_para_relevance, client, batch)
        ))
        # 6. Plagiarism
        tasks.append(asyncio.ensure_future(
            _safe_call(check_plagiarism, client, batch)
        ))

    # Fire everything concurrently — exceptions are returned, not raised
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten: each result is either a list of dicts or an Exception
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