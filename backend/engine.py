"""
engine.py — one switch for every check: our own local models or the Claude API.

    ENGINE=api    (default) every check uses the old Claude code, nothing changes.
    ENGINE=local  use our trained local model; ask Claude only when the local
                  model is unsure (confidence below the threshold).

Every result has the same small shape:
    {"label": ..., "confidence": 0.0-1.0 or None, "used_fallback": True/False}

Only detect_headings() is wired so far. The other checks are placeholders that
still call the old Claude/API code, so the project keeps working.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

# ── Config ───────────────────────────────────────────────────────────────────

ENGINE = os.getenv("ENGINE", "api").strip().lower()
if ENGINE not in ("api", "local"):
    print(f"[engine] Unknown ENGINE={ENGINE!r}, using 'api'")
    ENGINE = "api"

# Which local heading model: "v3" = text+context (works on unformatted input),
# "v2" = font size / bold / style (needs a formatted document).
HEADINGS_LOCAL_VERSION = os.getenv("HEADINGS_LOCAL_VERSION", "v3").strip().lower()

# Below this confidence the local answer is not trusted and Claude is asked.
# Change here, or with an env variable such as HEADINGS_THRESHOLD=0.8
THRESHOLDS: Dict[str, float] = {
    "headings": float(os.getenv("HEADINGS_THRESHOLD", "0.70")),
    "missing_sections": float(os.getenv("MISSING_SECTIONS_THRESHOLD", "0.70")),
    "para_relevance": float(os.getenv("PARA_RELEVANCE_THRESHOLD", "0.70")),
    "image_relevance": float(os.getenv("IMAGE_RELEVANCE_THRESHOLD", "0.70")),
    "image_ethics": float(os.getenv("IMAGE_ETHICS_THRESHOLD", "0.70")),
    "plagiarism": float(os.getenv("PLAGIARISM_THRESHOLD", "0.70")),
}


def make_result(label: Any, confidence: Optional[float], used_fallback: bool = False, **extra) -> Dict[str, Any]:
    """The one result shape every check returns."""
    return {
        "label": label,
        "confidence": None if confidence is None else round(float(confidence), 4),
        "used_fallback": bool(used_fallback),
        **extra,
    }


# ── 1. Heading detection (wired) ─────────────────────────────────────────────

async def detect_headings(
    client: Any,
    blocks: Sequence[Any],
    template: Optional[Dict[str, Any]] = None,
    *,
    use_style: bool = True,
) -> List[Dict[str, Any]]:
    """
    One result per block: label is H1 / H2 / H3 / Body / Caption.

    use_style: pass False for PDFs. The PDF parser guesses style_name itself,
    so it must not be treated like a real Word "Heading 1" style.
    """
    if ENGINE == "local" and HEADINGS_LOCAL_VERSION == "v3":
        from functions.heading_text import detect_headings_text
        return await detect_headings_text(client, blocks, template, threshold=THRESHOLDS["headings"])
    if ENGINE == "local":
        from functions.heading_local import detect_headings_local
        return await detect_headings_local(
            client, blocks, template,
            threshold=THRESHOLDS["headings"], use_style=use_style,
        )
    return await _headings_from_api(client, blocks, template)


async def _headings_from_api(client: Any, blocks: Sequence[Any], template=None) -> List[Dict[str, Any]]:
    """Old Claude path, converted to the common result shape.
    Claude only lists headings; it gives no score for the other lines, so their
    confidence is None."""
    from functions.heading_detect import detect_headings_api

    found = {c["paragraph_id"]: c for c in await detect_headings_api(client, blocks, template)}
    out = []
    for b in blocks:
        pid = getattr(b, "paragraph_id", "") or ""
        c = found.get(pid)
        if c:
            out.append(make_result(f"H{min(int(c['level']), 3)}", c.get("confidence"), paragraph_id=pid))
        else:
            out.append(make_result("Body", None, paragraph_id=pid))
    return out


# ── 2-6. Placeholders: still the old Claude/API code (Task 2+) ───────────────
# They pass all arguments straight through and return what the old code returns.

async def check_para_relevance(*args, **kwargs):
    from functions.para_relevance import check_para_relevance as old
    return await old(*args, **kwargs)


async def check_image_relevance(*args, **kwargs):
    from functions.image_relevance import check_image_relevance as old
    return await old(*args, **kwargs)


async def check_image_ethics(*args, **kwargs):
    from functions.image_ethics import check_image_ethics as old
    return await old(*args, **kwargs)


async def check_plagiarism(*args, **kwargs):
    from functions.plagiarism import check_plagiarism as old
    return await old(*args, **kwargs)


def detect_missing_sections(*args, **kwargs):
    from missing_sections import detect_missing_sections as old
    return old(*args, **kwargs)
