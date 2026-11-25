"""
functions/grammar.py — Grammar, spelling and punctuation SUGGESTIONS.

Runs fully locally (no LLM API): pyspellchecker + the fine-tuned flan-t5 model
in brain/ml/models/t5_grammar_v3, via functions/grammar_local.py.
Suggestions are never auto-applied; the user decides in the Grammar tab.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from models import Batch
from functions import grammar_local


def _report_progress(done: int, total: int) -> None:
    try:
        from analysis_progress import grammar_progress
        grammar_progress(done, total)
    except Exception:
        pass


def _is_heading(style: str) -> bool:
    s = (style or "").lower()
    return any(s.startswith(h) for h in grammar_local.HEADING_STYLES)


def _skip_paragraph(style: str) -> bool:
    return (style or "").lower().startswith("toc")  # table-of-contents lines


def check_paragraphs(
    paragraphs,
    *,
    use_model: Optional[bool] = None,
    on_update: Optional[Callable[[List[Dict[str, Any]], int, int], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
    progress: Optional[Callable[[int, int], None]] = _report_progress,
) -> List[Dict[str, Any]]:
    """Synchronous core: ParagraphBlock list → Issue-compatible dicts.
    `on_update(issues, done, total)` streams the converted issue list: spell-checker
    results first, then again after every model batch (see grammar_local.check)."""
    paras = [p for p in paragraphs if (p.text or "").strip() and not _skip_paragraph(p.style)]
    t0 = time.time()
    upd = None
    if on_update is not None:
        def upd(found, done, total):
            on_update(_to_issues(paras, found), done, total)
    try:
        # Headings/titles/captions: spell-check only (the model is for sentences).
        heading_units = [i for i, p in enumerate(paras) if _is_heading(p.style)]
        found = grammar_local.check([p.text for p in paras], progress=progress,
                                    spell_only_units=heading_units, use_model=use_model,
                                    on_update=upd, cancelled=cancelled)
    except Exception as exc:  # grammar must never break the report
        print(f"[grammar] check failed, returning no suggestions: {exc}")
        return []

    result = _to_issues(paras, found)
    n_sent = len({(i["unit_index"], i["sentence_index"]) for i in found})
    status = grammar_local.model_status()
    mode = "spell+model" if (status["loaded"] and use_model is not False) else "spell-only"
    print(
        f"[grammar] {len(paras)} paragraphs -> {len(result)} suggestions "
        f"in {n_sent} sentences ({mode}) in {time.time() - t0:.1f}s",
        flush=True,
    )
    return result


def _to_issues(paras, found: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for iss in found:
        p = paras[iss["unit_index"]]
        result.append({
            "function": "grammar",
            "type": "grammar",                       # unchanged: frontend filters on this
            "severity": "minor",
            "paragraph_id": p.paragraph_id,
            "image_id": "",
            "page": p.page_number,
            "reason": iss["reason"],
            "suggestion": iss["suggestion"],
            "explanation": iss["reason"],
            "original": iss["original"],
            "current_heading": "",
            "content_belongs_to": "",
            "text_preview": iss["original"][:120],
            "verdict": "",
            "confidence": 0,
            # optional extras (new)
            "source": iss["source"],                 # spell | model | both
            "grammar_type": iss["grammar_type"],     # spelling | grammar | punctuation
            "char_start": iss["char_start"],
            "char_end": iss["char_end"],
            "sentence_index": iss["sentence_index"],
            "sentence": iss["sentence"],
        })
    return result


async def check_grammar(client: Any, batch: Batch) -> List[Dict[str, Any]]:
    """Same signature as before (`client` is unused now).

    Inside a background analysis job (grammar_stream bound to the document) the
    report only waits for the spell-checker; the model pass is started in its
    own thread and its suggestions are streamed to the Grammar tab
    (GET /api/documents/grammar-stream/{id}). Anywhere else the model runs
    inline as before, in a worker thread so the event loop keeps running."""
    if not batch.paragraphs:
        return []
    import grammar_stream
    key = grammar_stream.current_key()
    if key is None or not grammar_local._env_bool("GRAMMAR_USE_MODEL", True):
        return await asyncio.to_thread(check_paragraphs, batch.paragraphs)
    spell_issues = await asyncio.to_thread(check_paragraphs, batch.paragraphs,
                                           use_model=False, progress=None)
    grammar_stream.start(key, batch.paragraphs, spell_issues)
    return spell_issues
