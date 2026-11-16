"""
functions/heading_resolver.py — Deterministic, template-anchored heading resolver.

WHY THIS EXISTS
---------------
Heading levels used to be decided independently by two LLM calls
(heading_detect.py and formatting.py) that never saw the whole document and
never agreed with each other. This module makes ONE decision, deterministically:

  1. DETECTION (LLM / style)  -> "is this paragraph a heading?"  (candidates only)
  2. RESOLUTION (this module) -> "which template section is it, and what level?"
  3. FORMATTING (LLM)         -> fonts / spacing / alignment only. It no longer
                                 decides heading levels; it receives the resolved
                                 outline and diffs it against the current style.

Algorithm
---------
  a. Normalise titles: strip typed numbering ("1.6.", "2)", "Chapter 3 —", ": "),
     case/plural/ampersand folding. Typed numbers are NEVER trusted for level.
  b. Order-aware alignment (weighted LCS / DP) between template sections and
     candidate headings. Alignment is global, so a list item like "3) Implementation"
     inside an SDLC paragraph cannot steal the "Implementation" chapter slot.
  c. Matched heading  -> level comes from the template (authoritative).
     Unmatched heading -> level inferred from structure:
        * compound parent rule  ("Assumptions & Constraints" -> children
          "Assumptions", "Constraints" become level+1)
        * relative-depth rule   (keep the author's relative nesting, re-based on the
          previous resolved heading, never skipping a level)
        * front matter -> level 1
  d. Unmatched "N)" / bullet candidates are list items, not headings.
  e. Template sections with no match are reported as missing, with an insert point.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

MATCH_THRESHOLD = 0.86
REVIEW_THRESHOLD = 0.70  # below this -> flag for (optional) LLM / human review

# "2) Foo", "a) Foo", "(3) Foo", "• Foo"
_LIST_MARKER_RE = re.compile(r"^\s*(?:\(?\d{1,2}\)|\(?[A-Za-z]\)|[•▪●○◦\-–—*])\s+\S")
_CAPTION_RE = re.compile(r"^\s*(figure|fig\.|table)\s*\d+", re.I)
# typed numbering we strip: "Chapter 3 —", "1.6.", "2)", "7.1. :", repeated ("2. 2)")
_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"(?:chapter|section|part)\s+\w+\s*[:.\-–—]*\s*"
    r"|\d+(?:\.\d+)+\.?\s*[:.\-–—]*\s*"
    r"|\d+[.)]\s*[:.\-–—]*\s*"
    r"|[:.\-–—]+\s*"
    r")+",
    re.I,
)
_STATUS_SUFFIX_RE = re.compile(r"\s*[—–-]\s*(implemented|addressed|partially.*|pending)\s*$", re.I)


# ------------------------------------------------------------------ helpers
def strip_numbering(text: str) -> tuple[str, str]:
    """Return (clean_text, removed_prefix)."""
    m = _PREFIX_RE.match(text or "")
    if not m:
        return (text or "").strip(), ""
    return text[m.end():].strip(), text[: m.end()].strip()


def normalize(text: str) -> str:
    clean, _ = strip_numbering(text)
    clean = _STATUS_SUFFIX_RE.sub("", clean).lower().replace("&", " and ")
    clean = re.sub(r"[^a-z0-9 ]+", " ", clean)
    toks = [t[:-1] if len(t) > 3 and t.endswith("s") else t for t in clean.split()]
    return " ".join(toks)


def style_level(style: str) -> Optional[int]:
    m = re.match(r"heading\s*([1-9])", (style or "").replace("_", " ").strip(), re.I)
    return int(m.group(1)) if m else None


def _score(t_norm: str, c_norm: str) -> float:
    if not t_norm or not c_norm:
        return 0.0
    if t_norm == c_norm:
        return 1.0
    ratio = difflib.SequenceMatcher(None, t_norm, c_norm).ratio()
    tt, ct = set(t_norm.split()), set(c_norm.split())
    if tt <= ct and len(ct) <= len(tt) + 2:  # template name contained in short title
        ratio = max(ratio, 0.9)
    return ratio if ratio >= MATCH_THRESHOLD else 0.0


def _compound_parts(norm_name: str) -> List[str]:
    """'assumption and constraint' -> ['assumption', 'constraint']"""
    parts = [p.strip() for p in norm_name.split(" and ") if p.strip()]
    return parts if len(parts) >= 2 else []


# ------------------------------------------------------------------ main
@dataclass
class Resolved:
    paragraph_id: str
    text: str
    clean_text: str
    stale_prefix: str
    current_level: Optional[int]
    expected_level: int
    kind: str  # heading | list_item
    template_index: Optional[int] = None
    template_name: str = ""
    reason: str = ""
    confidence: float = 0.0
    out_of_order: bool = False
    needs_review: bool = False


def resolve_headings(
    candidates: Sequence[Dict[str, Any]],
    required_sections: Sequence[Any],
) -> Dict[str, Any]:
    """
    candidates: doc-ordered [{paragraph_id, text, style?, hint_level?}]
        hint_level = existing Heading style level, or the detector's relative-depth
        guess. Only DIFFERENCES between hints are used, never the absolute value.
    required_sections: template sections [{name, heading_level, aliases?}] (or str).
    """
    tpl = []
    for s in required_sections or []:
        if isinstance(s, dict):
            name, lvl = str(s.get("name", "")).strip(), int(s.get("heading_level", 1) or 1)
            aliases = [str(a) for a in (s.get("aliases") or [])]
        else:
            name, lvl, aliases = str(s).strip(), 1, []
        if name:
            tpl.append({
                "name": name, "level": max(1, min(4, lvl)),
                "norms": [normalize(name)] + [normalize(a) for a in aliases],
            })

    cands = []
    for c in candidates:
        text = (c.get("text") or "").strip()
        if not text or _CAPTION_RE.match(text):
            continue
        clean, prefix = strip_numbering(text)
        lvl = style_level(c.get("style", ""))
        hint = c.get("hint_level") or lvl
        cands.append({
            "pid": c["paragraph_id"], "text": text, "clean": clean, "prefix": prefix,
            "norm": normalize(text), "marker": bool(_LIST_MARKER_RE.match(text) or re.search(r"[0-9A-Za-z]\)", prefix)),
            "cur": lvl, "hint": int(hint) if hint else None,
        })

    m, n = len(tpl), len(cands)
    S = [[0.0] * n for _ in range(m)]
    for i, t in enumerate(tpl):
        for j, c in enumerate(cands):
            s = max(_score(tn, c["norm"]) for tn in t["norms"])
            S[i][j] = s * (0.9 if c["marker"] else 1.0)

    # ---- pass 1: order-preserving weighted LCS
    dp = [[0.0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            best = max(dp[i - 1][j], dp[i][j - 1])
            if S[i - 1][j - 1] > 0:
                best = max(best, dp[i - 1][j - 1] + S[i - 1][j - 1])
            dp[i][j] = best
    match: Dict[int, int] = {}  # cand idx -> tpl idx
    i, j = m, n
    while i > 0 and j > 0:
        if dp[i][j] == dp[i][j - 1]:
            j -= 1
        elif dp[i][j] == dp[i - 1][j]:
            i -= 1
        else:
            match[j - 1] = i - 1
            i, j = i - 1, j - 1
    # ---- pass 2: leftover template entries, out of order (never for list markers)
    used_t = set(match.values())
    out_of_order = set()
    for ti in range(m):
        if ti in used_t:
            continue
        best_j, best_s = None, 0.0
        for cj in range(n):
            if cj in match or cands[cj]["marker"]:
                continue
            if S[ti][cj] > best_s:
                best_j, best_s = cj, S[ti][cj]
        if best_j is not None:
            match[best_j] = ti
            used_t.add(ti)
            out_of_order.add(best_j)

    # ---- level resolution (document order)
    results: List[Resolved] = []
    prev_new: Optional[int] = None
    prev_hint: Optional[int] = None
    prev_match_ti: Optional[int] = None
    anchor_compound: Optional[tuple[int, List[str]]] = None  # (child_level, parts)
    last_matched_j = max(match) if match else -1
    seen_matched = False

    for j, c in enumerate(cands):
        ti = match.get(j)
        # an exact repeat of an already matched template name (e.g. 3x "Software
        # Architecture Diagram") keeps that template's level
        dup_ti = None
        if ti is None:
            for k, t in enumerate(tpl):
                if k in used_t and max(_score(tn, c["norm"]) for tn in t["norms"]) >= 1.0 and not c["marker"]:
                    dup_ti = k
                    break

        if ti is None and dup_ti is None and c["marker"]:
            results.append(Resolved(c["pid"], c["text"], c["clean"], c["prefix"], c["cur"], 0,
                                    "list_item", reason="list marker with no template match",
                                    confidence=0.9))
            continue

        if ti is not None:
            t = tpl[ti]
            new, conf = t["level"], max(S[ti][j], 0.8)
            reason = "template match" + (" (out of order)" if j in out_of_order else "")
            name = t["name"]
            seen_matched = True
            parts = _compound_parts(t["norms"][0])
            anchor_compound = (new + 1, parts) if parts else None
            prev_match_ti = ti
        elif dup_ti is not None:
            new, conf, reason, name, ti = tpl[dup_ti]["level"], 0.85, "duplicate of template section", tpl[dup_ti]["name"], dup_ti
            anchor_compound = None
        else:
            name = ""
            conf = 0.6
            if anchor_compound and any(
                c["norm"] == p or c["norm"].startswith(p + " ") for p in anchor_compound[1]
            ):
                new, conf, reason = anchor_compound[0], 0.9, "part of compound parent section"
            elif prev_new is None:
                new, reason = 1, "front matter"
            else:
                delta = (c["hint"] - prev_hint) if (c["hint"] and prev_hint) else 1
                raw = prev_new + delta
                new = min(raw, prev_new + 1)  # never skip a level
                allow_h1 = (not seen_matched) or j > last_matched_j
                new = max(new, 1 if allow_h1 else 2)
                reason = "relative depth under previous heading"
                conf = 0.8 if new == raw and (c["hint"] and prev_hint) else 0.6
        new = max(1, min(4, new))

        r = Resolved(c["pid"], c["text"], c["clean"], c["prefix"], c["cur"], new, "heading",
                     template_index=ti, template_name=name, reason=reason, confidence=round(conf, 2),
                     out_of_order=j in out_of_order)
        r.needs_review = conf < REVIEW_THRESHOLD or r.out_of_order
        results.append(r)
        prev_new, prev_hint = new, c["hint"]

    # ---- missing template sections (+ where to insert them)
    matched_by_t = {r.template_index: r for r in results if r.template_index is not None and r.kind == "heading" and r.reason.startswith("template")}
    missing = []
    for ti, t in enumerate(tpl):
        if ti in matched_by_t:
            continue
        nxt = next((matched_by_t[k] for k in range(ti + 1, m) if k in matched_by_t), None)
        missing.append({"name": t["name"], "level": t["level"],
                        "insert_before_paragraph_id": nxt.paragraph_id if nxt else None})

    headings = [r for r in results if r.kind == "heading"]
    return {
        "headings": headings,
        "list_items": [r for r in results if r.kind == "list_item"],
        "missing_sections": missing,
        "changes": [r for r in headings if r.current_level != r.expected_level],
        "stale_prefixes": [r for r in headings if r.stale_prefix],
        "needs_review": [r for r in headings if r.needs_review],
    }