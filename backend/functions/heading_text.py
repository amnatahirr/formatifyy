"""
functions/heading_text.py — v3 heading detector: TEXT and CONTEXT only.

Why: real input documents are flat (same font, no bold, no Word heading
styles), so font_size / bold / style_name carry no signal. v3 decides from:
  - the line itself (length, punctuation, capitals, numbering, vocabulary)
  - its neighbours (is the next line a long paragraph? did the previous end with '.'?)
  - its position in the document

text_context_features() is used BOTH for training (brain/ml/train_headings_v3.py)
and in the live app, so features are always computed the same way.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from functions.heading_local import (
    CAP_STRONG, CAP_WEAK, CHAP, LABELS, ML_DIR, PAGE_BARE, PAGE_FOOTER, TOC_LEADER, num_level,
)

VOCAB_PATH = Path(__file__).with_name("heading_vocab.txt")
STOPWORDS = set("""a an the and or but of in on at to for from by with as is are was were be been
this that these those it its into than then so such which who whom whose what when where why how
not no can could should would will shall may might must do does did has have had our we you they he she
i my your their there here also very all any each some more most other""".split())
BULLET = re.compile(r"^\s*([•\-–*●▪◦►✓]|[a-z]\)|\(?[ivx]+\)|\(?[a-z]\))\s+", re.I)
NUM_START = re.compile(r"^\s*\(?\d+(\.\d+)*[.)]?\s")
LONG = 15   # a line with more than 15 words counts as a "long" paragraph


def load_vocab(path: Path = VOCAB_PATH) -> List[str]:
    lines = [l.strip().lower() for l in path.read_text(encoding="utf-8").splitlines()]
    return sorted({l for l in lines if l and not l.startswith("#")}, key=len, reverse=True)


VOCAB = load_vocab()
_VOCAB_SET = set(VOCAB)
_VOCAB_RE = re.compile(r"\b(" + "|".join(re.escape(v) for v in VOCAB) + r")\b")


def core_text(t: str) -> str:
    """'2.1 Problem Statement:' -> 'problem statement' (no numbering, no end punctuation)."""
    t = re.sub(r"^\s*(chapter\s*\d+\s*[:.\-–]?|\(?\d+(\.\d+)*[.)]?)\s*", "", t.strip(), flags=re.I)
    t = re.sub(r"[\s:.\-–—]+$", "", t)
    return " ".join(t.lower().split())


def _line(t: str) -> Dict[str, float]:
    t = t.strip()
    words = t.split()
    nw = len(words)
    letters = [c for c in t if c.isalpha()]
    alpha_words = [w for w in words if any(c.isalpha() for c in w)]
    core = core_text(t)
    return {
        "n_words": float(nw),
        "n_chars": float(len(t)),
        "ends_period": float(t.endswith(".")),
        "ends_colon": float(t.endswith(":")),
        "has_colon_inside": float(":" in t[:-1]),
        "title_case_ratio": (sum(w[0].isupper() for w in alpha_words) / len(alpha_words)) if alpha_words else 0.0,
        "all_caps_ratio": (sum(w.isupper() for w in alpha_words) / len(alpha_words)) if alpha_words else 0.0,
        "upper_letter_ratio": (sum(c.isupper() for c in letters) / len(letters)) if letters else 0.0,
        "num_level": float(num_level(t)),
        "starts_number": float(bool(NUM_START.match(t))),
        "is_chapter": float(bool(CHAP.match(t))),
        "starts_bullet": float(bool(BULLET.match(t))),
        "digit_ratio": (sum(c.isdigit() for c in t) / len(t)) if t else 0.0,
        "stopword_ratio": (sum(w.lower().strip(".,:;()") in STOPWORDS for w in words) / nw) if nw else 0.0,
        "is_question": float(t.endswith("?")),
        "starts_lower": float(t[:1].islower()),
        "caption_strong": float(bool(CAP_STRONG.match(t))),
        "caption_weak": float(bool(CAP_WEAK.match(t))),
        "dot_leader": float(bool(TOC_LEADER.search(t))),
        "page_like": float(bool(PAGE_BARE.match(t) or PAGE_FOOTER.match(t))),
        "vocab_exact": float(core in _VOCAB_SET),
        "vocab_contains": float(bool(_VOCAB_RE.search(core))) if nw <= LONG else 0.0,
    }


LINE_FEATURES = list(_line("x").keys())
CONTEXT_FEATURES = [
    "prev_n_words", "next_n_words", "next_is_long", "prev_ends_period",
    "next_starts_lower", "prev_num_level", "next_num_level",
    "rel_position", "is_first_of_block", "is_doc_start",
]
FEATURES_V3 = LINE_FEATURES + CONTEXT_FEATURES


def text_context_features(texts: Sequence[str]) -> List[List[float]]:
    """Features for every line of ONE document, in reading order.
    Only the text is used - no font size, bold or style."""
    lines = [(t or "").strip() for t in texts]
    base = [_line(t) for t in lines]
    n = len(lines)
    rows = []
    for i, f in enumerate(base):
        prev = base[i - 1] if i > 0 else None
        nxt = base[i + 1] if i + 1 < n else None
        ctx = {
            "prev_n_words": prev["n_words"] if prev else -1.0,
            "next_n_words": nxt["n_words"] if nxt else -1.0,
            "next_is_long": float(bool(nxt) and nxt["n_words"] > LONG),
            "prev_ends_period": float(bool(prev) and lines[i - 1].endswith(".")),
            "next_starts_lower": float(bool(nxt) and lines[i + 1][:1].islower()),
            "prev_num_level": prev["num_level"] if prev else -1.0,
            "next_num_level": nxt["num_level"] if nxt else -1.0,
            "rel_position": i / (n - 1) if n > 1 else 0.0,
            # first short line after a long paragraph (or at the start) = start of a new block
            "is_first_of_block": float(f["n_words"] <= LONG and (prev is None or prev["n_words"] > LONG)),
            "is_doc_start": float(i == 0),
        }
        rows.append([f[k] for k in LINE_FEATURES] + [ctx[k] for k in CONTEXT_FEATURES])
    return rows


# ── Model + live app entry point ─────────────────────────────────────────────

DEFAULT_V3_PATH = ML_DIR / "models" / "headings_xgb_v3.json"
_MODEL = None


def load_model_v3(path: Optional[Path] = None):
    global _MODEL
    if _MODEL is None:
        from xgboost import XGBClassifier
        p = Path(path or os.getenv("HEADINGS_V3_MODEL_PATH", str(DEFAULT_V3_PATH)))
        if not p.is_absolute() and not p.exists():
            p = ML_DIR / p
        if not p.exists():
            raise FileNotFoundError(f"No v3 model at {p}. Run brain/ml/train_headings_v3.py first.")
        m = XGBClassifier()
        m.load_model(str(p))
        _MODEL = m
    return _MODEL


def predict_v3(texts: Sequence[str], model=None):
    """(label, confidence) per line. Heading-or-not is decided first, on the SUM of
    the H classes (same as v4 training). The level is only a hint; the template sets the style."""
    import numpy as np
    if not texts:
        return []
    proba = (model or load_model_v3()).predict_proba(
        np.asarray(text_context_features(texts), dtype=float))
    h_ids = [i for i, l in enumerate(LABELS) if l[0] == "H" and l[1:].isdigit()]
    o_ids = [i for i in range(len(LABELS)) if i not in h_ids]
    head = proba[:, h_ids].sum(axis=1)
    out = []
    for i, p in enumerate(head):
        ids = h_ids if p >= 0.5 else o_ids
        k = ids[int(proba[i, ids].argmax())]
        out.append((LABELS[k], float(max(p, 1 - p))))
    return out


def formatting_marked_ratio(blocks: Sequence[Any]) -> float:
    """Share of short lines (<= 15 words) that carry a formatting mark:
    bold, a Word 'Heading' style, or a font >= 1pt bigger than the body font.
    Unknown font size (None) is not counted as a mark."""
    from functions.heading_local import body_font_size, style_heading_level
    texts = [(getattr(b, "text", "") or "").strip() for b in blocks]
    body = body_font_size((t, getattr(b, "font_size", None)) for t, b in zip(texts, blocks))
    short = [(t, b) for t, b in zip(texts, blocks) if t and len(t.split()) <= LONG]
    if not short:
        return 0.0
    marked = 0
    for t, b in short:
        fs = getattr(b, "font_size", None)
        if getattr(b, "bold", None) or style_heading_level(getattr(b, "style_name", None)) \
                or (fs and body and fs >= body + 1):
            marked += 1
    return marked / len(short)


def is_flat_document(blocks: Sequence[Any]) -> bool:
    from engine import FLAT_DOC_MAX_MARKED
    return formatting_marked_ratio(blocks) < FLAT_DOC_MAX_MARKED


async def detect_headings_text(
    client: Any,
    blocks: Sequence[Any],
    template: Optional[Dict[str, Any]] = None,
    *,
    threshold: float = 0.70,
) -> List[Dict[str, Any]]:
    """Live app entry point for v3: label every block from text + context,
    then ask Claude about blocks below the threshold."""
    from engine import make_result
    from functions.heading_local import apply_claude_fallback

    from engine import FLAT_DOC_CONFIDENCE_FACTOR

    texts = [(getattr(b, "text", "") or "") for b in blocks]
    flat = is_flat_document(blocks)
    factor = FLAT_DOC_CONFIDENCE_FACTOR if flat else 1.0
    results = [
        make_result(label, conf * factor, paragraph_id=getattr(b, "paragraph_id", "") or "", flat_document=flat)
        for b, (label, conf) in zip(blocks, predict_v3(texts))
    ]
    if flat:
        print(f"[heading_text] flat document: confidences x{factor}")
    return await apply_claude_fallback(client, blocks, results, template, threshold)
