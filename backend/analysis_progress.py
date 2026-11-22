"""
analysis_progress.py — real progress for the background analysis job.

The background worker binds its job dict with `bind(job)`; any code running
inside that analysis (also in worker threads started with asyncio.to_thread,
which copy context variables) can call `set_stage(...)` / `grammar_progress(...)`.
Outside an analysis job these calls do nothing.

GET /api/documents/analyze-status/{id} returns job["progress"]:
    {"stage": "grammar", "percent": 57, "detail": "Sentence 40 of 96"}
"""

from __future__ import annotations

import contextvars
import time
from typing import Any, Dict, Optional

# Stage key -> (start %, end %), in the order the pipeline runs them.
STAGES: Dict[str, tuple] = {
    "preparing": (0, 8),     # template formatting of the working copy
    "reading": (8, 15),      # parse document
    "structure": (15, 25),   # heading outline
    "grammar": (25, 90),     # grammar + other checks (grammar is the slowest)
    "formatting": (90, 95),  # final reformat
    "finalizing": (95, 99),  # preview blocks, saving
}

_JOB: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "analysis_progress_job", default=None
)


def bind(job: Dict[str, Any]) -> contextvars.Token:
    job["progress"] = {"stage": "preparing", "percent": 0, "detail": "", "updated_at": time.time()}
    return _JOB.set(job)


def _write(stage: str, percent: float, detail: str = "") -> None:
    job = _JOB.get()
    if job is None:
        return
    prev = job.get("progress") or {}
    # never go backwards (parallel tasks may report out of order)
    percent = max(float(prev.get("percent", 0)), percent)
    job["progress"] = {
        "stage": stage,
        "percent": int(min(percent, 99)),
        "detail": detail,
        "updated_at": time.time(),
    }


def set_stage(stage: str, detail: str = "") -> None:
    start, _ = STAGES.get(stage, (0, 0))
    _write(stage, start, detail)


def grammar_progress(done: int, total: int) -> None:
    start, end = STAGES["grammar"]
    frac = (done / total) if total else 1.0
    _write("grammar", start + (end - start) * frac, f"Grammar: sentence {done} of {total}")
