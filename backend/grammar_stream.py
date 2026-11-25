"""
grammar_stream.py — stream grammar-model suggestions after the report is ready.

Inside a background analysis job (`bind(document_id)` in main._analysis_worker)
functions/grammar.check_grammar returns the spell-checker suggestions straight
away and calls `start(...)`, which runs the slow T5 model pass in its own
thread. Every finished model batch replaces the document's grammar issue list
here; the Grammar tab polls GET /api/documents/grammar-stream/{id} and shows
progress + new suggestions as they arrive.

When the pass finishes, the saved analysis result (uploads/analysis/doc_N.json)
is patched so reloading the report shows the final grammar suggestions.
`attach_result` and the end of the pass may happen in either order; whichever
comes second does the patch.
"""

from __future__ import annotations

import contextvars
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_KEY: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("grammar_stream_key", default=None)
_LOCK = threading.Lock()
_STREAMS: Dict[str, Dict[str, Any]] = {}


def bind(document_id: Any) -> contextvars.Token:
    return _KEY.set(str(document_id))


def current_key() -> Optional[str]:
    return _KEY.get()


# ── issue conversion (same steps the analysis applies: dedupe → Issue → normalize)

def to_result_issues(raw_issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from issue_utils import normalize_issue
    from models import Issue

    out, seen = [], set()
    for idx, raw in enumerate(raw_issues):
        key = (raw.get("paragraph_id"), raw.get("char_start"), raw.get("char_end"))
        if key in seen:
            continue
        seen.add(key)
        clean = {k: v for k, v in raw.items() if not k.startswith("_") and v is not None}
        out.append(normalize_issue(Issue(**clean).model_dump(), {}, idx))
    return out


# ── state ───────────────────────────────────────────────────────────────────

def start(key: str, paragraphs: list, spell_issues: List[Dict[str, Any]]) -> str:
    """Start the model pass for document `key`; replaces (cancels) an older pass."""
    run_id = uuid.uuid4().hex
    with _LOCK:
        _STREAMS[key] = {
            "run_id": run_id,
            "status": "running",
            "done": 0,
            "total": 0,
            "version": 0,
            "issues": to_result_issues(spell_issues),
            "error": "",
            "started_at": time.time(),
            "finished_at": None,
            "result_path": None,
            "patched": False,
        }
    threading.Thread(target=_run, args=(key, run_id, paragraphs),
                     name=f"grammar-stream-{key}", daemon=True).start()
    return run_id


def _current(key: str, run_id: str) -> Optional[Dict[str, Any]]:
    st = _STREAMS.get(key)
    return st if st is not None and st["run_id"] == run_id else None


def _publish(key: str, run_id: str, raw: List[Dict[str, Any]], done: int, total: int) -> None:
    issues = to_result_issues(raw)
    with _LOCK:
        st = _current(key, run_id)
        if st is None:
            return
        st.update(issues=issues, done=done, total=total, version=st["version"] + 1)


def _run(key: str, run_id: str, paragraphs: list) -> None:
    from functions import grammar_local
    from functions.grammar import check_paragraphs

    t0 = time.time()
    error = ""
    try:
        final = check_paragraphs(
            paragraphs,
            on_update=lambda raw, d, t: _publish(key, run_id, raw, d, t),
            cancelled=lambda: _STREAMS.get(key, {}).get("run_id") != run_id,
            progress=None,
        )
        status = grammar_local.model_status()
        if status["failed"]:
            error = "Grammar model unavailable — spelling suggestions only."
    except Exception as exc:  # never crash the server thread
        final, error = None, f"Grammar model failed: {exc}"

    with _LOCK:
        st = _current(key, run_id)
        if st is None:
            return  # a newer analysis replaced this pass
        if final is not None:
            st["issues"] = to_result_issues(final)
        st.update(status="failed" if final is None else "done", error=error,
                  done=st["total"], finished_at=time.time(), version=st["version"] + 1)
        print(f"[grammar-stream] doc {key}: model pass {st['status']} in {time.time() - t0:.1f}s "
              f"({len(st['issues'])} suggestions)", flush=True)
        if st["result_path"]:
            _patch_result_locked(st)


def meta(key: Any) -> Optional[Dict[str, Any]]:
    """Small status block stored in the saved analysis result."""
    st = _STREAMS.get(str(key))
    if st is None:
        return None
    return {"run_id": st["run_id"], "status": st["status"], "done": st["done"],
            "total": st["total"], "error": st["error"]}


def snapshot(key: Any, since: int = -1) -> Dict[str, Any]:
    """Payload for GET grammar-stream. Issues are left out when the client
    already has version `since`."""
    with _LOCK:
        st = _STREAMS.get(str(key))
        if st is None:
            return {"status": "none"}
        out = {k: st[k] for k in ("run_id", "status", "done", "total", "version", "error")}
        if st["version"] > since:
            out["issues"] = list(st["issues"])
        return out


def attach_result(key: Any, path: str) -> None:
    """Called once the analysis result file is saved; patches it now if the
    model pass already finished, otherwise when it finishes."""
    with _LOCK:
        st = _STREAMS.get(str(key))
        if st is None:
            return
        st["result_path"] = path
        if st["status"] != "running":
            _patch_result_locked(st)


def _patch_result_locked(st: Dict[str, Any]) -> None:
    if st["patched"]:
        return
    path = st["result_path"]
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if (data.get("grammar_stream") or {}).get("run_id") != st["run_id"]:
            return  # file belongs to another analysis run
        patch_result(data, st["issues"])
        data["grammar_stream"] = {"run_id": st["run_id"], "status": st["status"],
                                  "done": st["done"], "total": st["total"], "error": st["error"]}
        tmp = path + ".grammar.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, default=str)
        os.replace(tmp, path)
        st["patched"] = True
    except Exception as exc:
        print(f"[grammar-stream] could not patch {path}: {exc}", flush=True)


def _is_grammar(issue: Dict[str, Any]) -> bool:
    return str(issue.get("function") or "").lower() == "grammar"


def patch_result(data: Dict[str, Any], grammar_issues: List[Dict[str, Any]]) -> None:
    """Replace the grammar issues of an analysis result dict and fix the counts."""
    def replace(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pos = next((i for i, x in enumerate(lst) if _is_grammar(x)), 0)
        rest = [x for x in lst if not _is_grammar(x)]
        return rest[:pos] + list(grammar_issues) + rest[pos:]

    issues = replace(data.get("issues") or [])
    data["issues"] = issues
    if isinstance(data.get("content_issues"), list):
        data["content_issues"] = replace(data["content_issues"])
    if isinstance(data.get("stats"), dict):
        data["stats"]["grammar_issues"] = len(grammar_issues)
    summary = (data.get("structure") or {}).get("summary")
    if isinstance(summary, dict):
        summary["grammar"] = len(grammar_issues)
        if isinstance(data.get("content_issues"), list):
            summary["content_issues"] = len(data["content_issues"])
    sev = [(i.get("severity") or "") for i in issues]
    for key, n in (("total_issues", len(issues)),
                   ("minor_issues", sum(s.lower() == "minor" for s in sev)),
                   ("warning_issues", sum(s.upper() in ("WARNING", "MINOR") for s in sev))):
        if key in data:
            data[key] = n
