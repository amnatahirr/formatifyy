"""
functions/heading_local.py — local heading detection (no API needed).

Two local methods:
  1. rule_label()    : simple rules (font size, bold, numbering). First baseline.
  2. XGBoost model   : trained by brain/ml/train_headings.py on the same features.

IMPORTANT: block_features() is used BOTH for training and in the live app,
so the model always sees features computed in exactly the same way.
Only fields the app has at runtime are used: text, font_size, bold, style_name.
(page_number is left out: Word files have no real page number in training.)
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

LABELS = ["H1", "H2", "H3", "Body", "Caption"]   # class index 0..4 in the model

# Same patterns as brain/ml/auto_label.py
NUM = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(?=\S)")
CHAP = re.compile(r"^\s*(chapter|appendix)\s*:?\s*[\dA-Z]+", re.I)
CAP_STRONG = re.compile(r"^\s*(figure|fig\.|table)\s*\d+(\.\d+)*\s*[:.\-–—]", re.I)
CAP_WEAK = re.compile(r"^\s*(figure|fig\.|table)\s*\d+(\.\d+)*\b", re.I)
PAGE_BARE = re.compile(r"^\s*(page\s*)?\d+\s*$", re.I)
PAGE_FOOTER = re.compile(r"^\s*(page\s*\d+|\d+\s+of\s+\d+)\b", re.I)
TOC_LEADER = re.compile(r"(\.\s*){5,}")
BULLET = re.compile(r"^\s*([•\-–*●▪◦]|[a-z]\)|\(?[ivx]+\))\s+", re.I)

ML_DIR = Path(__file__).resolve().parents[2] / "brain" / "ml"
DEFAULT_MODEL_PATH = ML_DIR / "models" / "headings_xgb.json"


def _model_path() -> Path:
    """HEADINGS_MODEL_PATH may be absolute, or relative like 'models/headings_xgb_v2.json'
    (then it is looked up inside brain/ml/, so it works from any folder)."""
    p = Path(os.getenv("HEADINGS_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
    if not p.is_absolute() and not p.exists():
        p = ML_DIR / p
    return p


MODEL_PATH = _model_path()


# ── Shared helpers ───────────────────────────────────────────────────────────

def num_level(t: str) -> int:
    """'3.2 System Architecture' -> 2, '2. Intro' -> 1, plain text -> 0."""
    m = NUM.match(t)
    if not m:
        return 0
    parts = m.group(1).split(".")
    rest = t[m.end():]
    if not rest or not rest[0].isalpha():
        return 0
    if len(parts) == 1 and not (int(parts[0]) <= 12 and rest[0].isupper()):
        return 0
    return len(parts)


def body_font_size(pairs: Iterable[Tuple[str, Optional[float]]]) -> Optional[float]:
    """Body font of a document = the font size that holds the most text.
    pairs = (text, font_size) for every block."""
    w: Counter = Counter()
    for text, size in pairs:
        if size:
            w[round(size, 1)] += len(text or "")
    return w.most_common(1)[0][0] if w else None


def style_heading_level(style_name: Optional[str]) -> int:
    m = re.match(r"Heading (\d)", style_name or "")
    return min(int(m.group(1)), 3) if m else 0


# ── 1. Rule baseline ─────────────────────────────────────────────────────────

def rule_label(text: str, font_size: Optional[float], bold: Optional[bool],
               style_name: Optional[str], body: Optional[float]) -> str:
    """Same rules as auto_label.py, mapped to the 5 classes.
    (Page numbers / TOC lines / 'Unsure' bold lines -> Body.)"""
    t = (text or "").strip()
    words = len(t.split())
    style = style_name or ""
    if PAGE_BARE.match(t) or PAGE_FOOTER.match(t) or TOC_LEADER.search(t):
        return "Body"
    if CAP_STRONG.match(t) and words <= 40:
        return "Caption"
    if CAP_WEAK.match(t) and words <= 12 and not t.endswith((".", ",", ";")):
        return "Caption"
    lvl = style_heading_level(style)
    if lvl:
        return f"H{lvl}"
    if style == "Caption":
        return "Caption"

    ratio = font_size / body if font_size and body else 1.0
    bold = bool(bold)
    if words <= 15 and not t.endswith((".", ",", ";")):
        n = num_level(t)
        if n == 1 and (words > 8 or not (bold or ratio >= 1.1)):
            return "Body"
        if n:
            return f"H{min(n, 3)}"
        if CHAP.match(t):
            return "H1"
        if bold and ratio >= 1.3:
            return "H1"
        if bold and ratio >= 1.15:
            return "H2"
    return "Body"


# ── 2. Features for XGBoost ──────────────────────────────────────────────────

FEATURES = [
    "size_ratio", "font_known", "bold", "num_level", "is_chapter",
    "n_words", "n_chars", "upper_ratio", "is_title_case",
    "ends_period", "ends_colon", "ends_other_punct",
    "caption_strong", "caption_weak", "dot_leader", "page_like",
    "starts_bullet", "starts_lower",
    "style_heading_level", "style_is_caption", "style_is_list",
]


def block_features(text: str, font_size: Optional[float], bold: Optional[bool],
                   style_name: Optional[str], body: Optional[float],
                   use_style: bool = True) -> List[float]:
    """Turn one text block into a list of numbers (same order as FEATURES).
    use_style=False (or no style) -> style features = -1 meaning 'unknown'."""
    t = (text or "").strip()
    letters = [c for c in t if c.isalpha()]
    words = len(t.split())
    ratio = (font_size / body) if (font_size and body) else math.nan
    style = style_name if (use_style and style_name) else None
    return [
        ratio,
        1.0 if font_size else 0.0,
        1.0 if bold else 0.0,
        float(num_level(t)),
        1.0 if CHAP.match(t) else 0.0,
        float(words),
        float(len(t)),
        (sum(c.isupper() for c in letters) / len(letters)) if letters else 0.0,
        1.0 if t.istitle() else 0.0,
        1.0 if t.endswith(".") else 0.0,
        1.0 if t.endswith(":") else 0.0,
        1.0 if t.endswith((",", ";", "?", "!")) else 0.0,
        1.0 if CAP_STRONG.match(t) else 0.0,
        1.0 if CAP_WEAK.match(t) else 0.0,
        1.0 if TOC_LEADER.search(t) else 0.0,
        1.0 if (PAGE_BARE.match(t) or PAGE_FOOTER.match(t)) else 0.0,
        1.0 if BULLET.match(t) else 0.0,
        1.0 if t[:1].islower() else 0.0,
        float(style_heading_level(style)) if style else -1.0,
        (1.0 if style == "Caption" else 0.0) if style else -1.0,
        (1.0 if "list" in style.lower() else 0.0) if style else -1.0,
    ]


# ── Model loading / prediction ───────────────────────────────────────────────

_MODEL = None


def load_model(path: Path = MODEL_PATH):
    """Load the trained XGBoost model once and keep it in memory."""
    global _MODEL
    if _MODEL is None:
        from xgboost import XGBClassifier
        if not path.exists():
            raise FileNotFoundError(f"No heading model at {path}. Run brain/ml/train_headings.py first.")
        m = XGBClassifier()
        m.load_model(str(path))
        _MODEL = m
    return _MODEL


def predict_rows(feature_rows: List[List[float]], model=None) -> List[Tuple[str, float]]:
    """(label, confidence) per row. Confidence = highest class probability."""
    import numpy as np
    if not feature_rows:
        return []
    model = model or load_model()
    proba = model.predict_proba(np.asarray(feature_rows, dtype=float))
    best = proba.argmax(axis=1)
    return [(LABELS[int(k)], float(proba[i, k])) for i, k in enumerate(best)]


# ── Live app entry point ─────────────────────────────────────────────────────

async def detect_headings_local(
    client: Any,
    blocks: Sequence[Any],
    template: Optional[Dict[str, Any]] = None,
    *,
    threshold: float = 0.70,
    use_style: bool = True,
) -> List[Dict[str, Any]]:
    """
    1. XGBoost labels every block and gives a confidence.
    2. Blocks with confidence < threshold are sent to Claude (if a client exists).
       Claude only answers "heading level N" or "not a heading":
         - heading      -> H1/H2/H3 from Claude
         - not a heading -> Body (or keep local Caption/Body guess)
    """
    from engine import make_result

    texts = [(getattr(b, "text", "") or "") for b in blocks]
    body = body_font_size((t, getattr(b, "font_size", None)) for t, b in zip(texts, blocks))
    feats = [
        block_features(t, getattr(b, "font_size", None), getattr(b, "bold", None),
                       getattr(b, "style_name", None), body, use_style)
        for t, b in zip(texts, blocks)
    ]
    preds = predict_rows(feats)

    results = [
        make_result(label, conf, paragraph_id=getattr(b, "paragraph_id", "") or "")
        for b, (label, conf) in zip(blocks, preds)
    ]

    return await apply_claude_fallback(client, blocks, results, template, threshold)


async def apply_claude_fallback(client, blocks, results, template, threshold) -> List[Dict[str, Any]]:
    """Send blocks with confidence < threshold to Claude (shared by v2 and v3)."""
    texts = [(getattr(b, "text", "") or "") for b in blocks]
    unsure = [i for i, r in enumerate(results) if r["confidence"] < threshold and texts[i].strip()]
    if not unsure or client is None:
        return results

    from functions.heading_detect import detect_headings_api
    claude = {c["paragraph_id"]: c for c in await detect_headings_api(client, [blocks[i] for i in unsure], template)}
    for i in unsure:
        r = results[i]
        c = claude.get(r["paragraph_id"])
        if c:
            r["label"], r["confidence"] = f"H{min(int(c['level']), 3)}", c.get("confidence")
        elif r["label"] not in ("Body", "Caption"):
            r["label"], r["confidence"] = "Body", None
        r["used_fallback"] = True
    print(f"[heading_local] {len(unsure)}/{len(blocks)} block(s) sent to Claude (threshold {threshold})")
    return results
