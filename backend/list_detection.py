"""
list_detection.py — Deterministic list/bullet detection pre-pass.

Detects list candidates BEFORE the LLM formatting audit so the model only
confirms / assigns list levels rather than deciding whether something is a
list at all.

Signals (any one is enough to seed a group; consecutive items merge):
  a) Bold/emphasized label + colon + description  ("Throughput: 120 req/s")
  b) Shared opening grammar across 2+ consecutive paragraphs:
       - infinitive  ("To develop…", "To build…")
       - gerund      ("Developing…", "Building…")
       - manual markers (-, *, •, a), i), 1.)
  c) Trigger line ending in "are:", "include:", "as follows:" (etc.) —
     every following body paragraph until a heading/topic shift is one list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ── Patterns ─────────────────────────────────────────────────────────────────

# Hierarchical section titles ("3.2. Proposed Solution") — NEVER list items.
_SECTION_HEADING_RE = re.compile(r"^\d+(?:\.\d+)+\.?\s+\S")
# Single-level list markers only. Reject "3.2." via (?!\d) after the first "3."
_BULLET_MARKER_RE = re.compile(
    r"^(?:"
    r"[•*○■▪\-–—→»·]"
    r"|\(?[A-Za-z][.)]"
    r"|\(?[ivxlcdmIVXLCDM]+[.)]"
    r"|\(?\d+[.)](?!\d)"  # "1. item" / "1) item" — not "3.2. Title"
    r")\s+"
)
_LABEL_COLON_RE = re.compile(
    r"^[A-Z][A-Za-z0-9\s/&()'\"-]{0,50}:\s+\S"
)
_BOLD_LABEL_COLON_RE = re.compile(
    r"^\*?\*?[A-Z][A-Za-z0-9\s/&()'\"-]{1,50}\*?\*?:\s+\S"
)
_INFINITIVE_RE = re.compile(r"^To\s+[a-z]+\b", re.IGNORECASE)
_GERUND_RE = re.compile(
    r"^[A-Z][a-z]*ing\b(?:\s|,|:|$)"  # Developing… / Building a…
)
_TRIGGER_LINE_RE = re.compile(
    r"(?:"
    r"\b(?:are|is|include|includes|including|comprise|comprises|"
    r"consist\s+of|consists\s+of|as\s+follows|the\s+following|"
    r"such\s+as|listed\s+below|outlined\s+below)\s*:"
    r"|:\s*$"
    r")\s*$",
    re.IGNORECASE,
)
_HEADING_STYLE_RE = re.compile(r"heading\s*\d|title|subtitle", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
# Infinitive objective sentences are always list body — never headings.
_OBJECTIVE_INFINITIVE_RE = re.compile(r"^To\s+[a-z]+\b.{10,}", re.IGNORECASE)


@dataclass
class ListItem:
    index: int
    paragraph_id: str
    text: str
    pattern: str  # marker | label_colon | infinitive | gerund | trigger_follower
    has_numpr: bool = False


@dataclass
class ListGroup:
    items: List[ListItem] = field(default_factory=list)
    trigger_index: Optional[int] = None
    trigger_text: str = ""
    detection: str = ""  # which signal primarily created the group

    @property
    def indices(self) -> List[int]:
        return [i.index for i in self.items]

    @property
    def paragraph_ids(self) -> List[str]:
        return [i.paragraph_id for i in self.items]


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _opening_signature(text: str) -> Optional[str]:
    """Return a grammar-opening signature used to cluster parallel items."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    # Never treat hierarchical section titles as list markers
    if _SECTION_HEADING_RE.match(stripped):
        return None
    cleaned = re.sub(r"^[•*○■▪\-–—→»·]\s+", "", stripped)
    if _SECTION_HEADING_RE.match(cleaned):
        return None
    if _BULLET_MARKER_RE.match(stripped):
        return "marker"
    if _LABEL_COLON_RE.match(cleaned) or _BOLD_LABEL_COLON_RE.match(cleaned):
        return "label_colon"
    if _INFINITIVE_RE.match(cleaned):
        return "infinitive"
    if _GERUND_RE.match(cleaned) and _word_count(cleaned) <= 40:
        return "gerund"
    return None


def _is_heading_like(
    text: str,
    style: str = "",
    *,
    known_heading: bool = False,
) -> bool:
    """
    True for real section headings that must never become list items.

    Includes Word Heading styles and decimal section titles like
    "3.2. Proposed Solution" / "1. Introduction".
    """
    if known_heading:
        return True
    if style and _HEADING_STYLE_RE.search(style):
        return True
    stripped = (text or "").strip()
    # Strip a stray bullet glyph if present — still evaluate the title beneath.
    stripped = re.sub(r"^[•*○■▪\-–—→»·]\s+", "", stripped)
    if not stripped:
        return False

    # Infinitive objectives are list body even when partially bolded.
    if _OBJECTIVE_INFINITIVE_RE.match(stripped) or _INFINITIVE_RE.match(stripped):
        return False

    # Single-level numbered module/list rows are list body, not headings.
    # Keep hierarchical "3.2. Title" and short "1. Introduction" as headings.
    if re.match(r"^\d+\.\s+\S", stripped) and not re.match(r"^\d+\.\d+", stripped):
        wc = _word_count(stripped)
        if ":" in stripped and wc >= 6:
            return False
        if wc > 8:
            return False
        # Short titles: "1. Introduction" / "2. Background"
        if wc <= 6 and ":" not in stripped:
            body = re.sub(r"^\d+\.\s+", "", stripped).strip()
            if body and not body.endswith((".", "?", "!")):
                return True

    # Hierarchical / ordered section titles
    if _SECTION_HEADING_RE.match(stripped):
        return True
    if re.match(r"^\d+\.\s+[A-Z].{0,80}$", stripped) and _word_count(stripped) <= 12:
        if not stripped.rstrip().endswith((".", "?", "!")) or stripped.count(".") <= 1:
            # "1. Introduction" — single trailing period on the number only
            if re.match(r"^\d+\.\s+\S", stripped) and not re.search(r"[.!?]\s+\S", stripped):
                return True

    words = _word_count(stripped)
    if words <= 10 and not _SENTENCE_END_RE.search(stripped) and not _opening_signature(stripped):
        # Title-case short lines often are headings — treat as list breakers
        title_body = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", stripped)
        if title_body.istitle() or title_body.isupper() or stripped.istitle() or stripped.isupper():
            return True
    return False


def is_heading_paragraph(text: str, style: str = "") -> bool:
    """Public helper used by bullet application to refuse heading targets."""
    return _is_heading_like(text, style)


def _is_trigger_line(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if _word_count(stripped) > 40:
        return False
    return bool(_TRIGGER_LINE_RE.search(stripped))


def _normalize_block(raw: Any, fallback_index: int) -> Dict[str, Any]:
    if isinstance(raw, dict):
        text = str(raw.get("text") or "").strip()
        idx = int(raw.get("index", raw.get("block_id", fallback_index)))
        pid = str(raw.get("paragraph_id") or f"p{idx}")
        style = str(raw.get("style") or raw.get("style_name") or "")
        has_numpr = bool(raw.get("has_numpr"))
        known_heading = (raw.get("type") or "").lower() == "heading"
        return {
            "index": idx,
            "paragraph_id": pid,
            "text": text,
            "style": style,
            "has_numpr": has_numpr,
            "known_heading": known_heading,
        }

    # ParagraphBlock-like object
    text = str(getattr(raw, "text", "") or "").strip()
    pid = str(getattr(raw, "paragraph_id", "") or f"p{fallback_index}")
    style = str(getattr(raw, "style_name", None) or getattr(raw, "style", "") or "")
    return {
        "index": fallback_index,
        "paragraph_id": pid,
        "text": text,
        "style": style,
        "has_numpr": False,
        "known_heading": bool(style and _HEADING_STYLE_RE.search(style)),
    }


def detect_list_groups(
    blocks: Sequence[Any],
    *,
    min_items: int = 2,
) -> List[ListGroup]:
    """
    Scan ordered paragraphs and return deterministic ListGroup detections.

    Does not require Word numPr — that is exactly what we are looking to fix.
    """
    normalized = [_normalize_block(b, i) for i, b in enumerate(blocks)]
    groups: List[ListGroup] = []

    i = 0
    n = len(normalized)
    while i < n:
        block = normalized[i]
        text = block["text"]
        if not text:
            i += 1
            continue

        if _is_heading_like(text, block["style"], known_heading=block["known_heading"]):
            i += 1
            continue

        # ── Signal (c): trigger line → following items until break ──────────
        if _is_trigger_line(text):
            group = ListGroup(
                trigger_index=block["index"],
                trigger_text=text,
                detection="trigger_line",
            )
            j = i + 1
            while j < n:
                nxt = normalized[j]
                nxt_text = nxt["text"]
                if not nxt_text:
                    j += 1
                    continue
                if _is_heading_like(
                    nxt_text, nxt["style"], known_heading=nxt["known_heading"]
                ):
                    break
                if _is_trigger_line(nxt_text):
                    break
                # Stop on long prose that doesn't share list signals once we
                # already have items AND the prose looks like a topic shift.
                sig = _opening_signature(nxt_text)
                if group.items and sig is None and _word_count(nxt_text) > 45:
                    break
                pattern = sig or "trigger_follower"
                group.items.append(
                    ListItem(
                        index=nxt["index"],
                        paragraph_id=nxt["paragraph_id"],
                        text=nxt_text,
                        pattern=pattern,
                        has_numpr=nxt["has_numpr"],
                    )
                )
                j += 1

            if len(group.items) >= min_items:
                groups.append(group)
                i = j
                continue
            # Fall through — maybe parallel grammar starts here instead

        # ── Signals (a)/(b): consecutive shared opening signatures ──────────
        sig = _opening_signature(text)
        if sig is None:
            i += 1
            continue

        group = ListGroup(detection=sig)
        j = i
        while j < n:
            cur = normalized[j]
            cur_text = cur["text"]
            if not cur_text:
                j += 1
                continue
            if _is_heading_like(
                cur_text, cur["style"], known_heading=cur["known_heading"]
            ):
                break
            cur_sig = _opening_signature(cur_text)
            if cur_sig != sig:
                break
            group.items.append(
                ListItem(
                    index=cur["index"],
                    paragraph_id=cur["paragraph_id"],
                    text=cur_text,
                    pattern=cur_sig,
                    has_numpr=cur["has_numpr"],
                )
            )
            j += 1

        if len(group.items) >= min_items:
            groups.append(group)
            i = j
            continue

        i += 1

    return _dedupe_groups(groups)


def _dedupe_groups(groups: List[ListGroup]) -> List[ListGroup]:
    seen = set()
    unique: List[ListGroup] = []
    for g in groups:
        key = tuple(g.indices)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(g)
    return unique


def groups_needing_numpr(groups: Sequence[ListGroup]) -> List[ListGroup]:
    """Filter to groups where at least one item lacks Word numbering."""
    result: List[ListGroup] = []
    for g in groups:
        missing = [item for item in g.items if not item.has_numpr]
        if len(missing) >= 2 or (len(missing) >= 1 and len(g.items) >= 2):
            # Keep only the missing items for fix application
            filtered = ListGroup(
                items=missing if len(missing) >= 2 else list(g.items),
                trigger_index=g.trigger_index,
                trigger_text=g.trigger_text,
                detection=g.detection,
            )
            if len(filtered.items) >= 2:
                result.append(filtered)
    return result


def list_groups_to_issues(
    groups: Sequence[ListGroup],
    *,
    issue_prefix: str = "list_detect",
) -> List[Dict[str, Any]]:
    """Convert detected groups lacking numPr into formatting issues."""
    issues: List[Dict[str, Any]] = []
    for gi, group in enumerate(groups_needing_numpr(groups)):
        para_indices = group.indices
        preview = [item.text[:60] for item in group.items[:3]]
        first = group.items[0]
        sibling_ids = ", ".join(group.paragraph_ids)
        reason = (
            f"Parallel list items detected via '{group.detection}' "
            f"(e.g. '{preview[0]}') need Word list styling. "
            f"Group paragraph_ids: {sibling_ids}."
        )
        issues.append({
            "issue_id": f"{issue_prefix}_{gi}_{first.index}",
            "paragraph_id": first.paragraph_id,
            "function": "formatting",
            "category": "Formatting",
            "type": "missing_bullets",
            "code": "MISSING_BULLETS",
            "severity": "minor",
            "reason": reason,
            "description": reason,
            "message": reason,
            "heading": "List formatting",
            "para_indices": para_indices,
            "para_index": first.index,
            "preview_items": preview,
            "suggestion": "Apply Word bullet list formatting",
            "fix_type": "apply_section_bullets",
            "fix_details": {"para_indices": para_indices},
            "list_detection": group.detection,
            "list_paragraph_ids": group.paragraph_ids,
            "source": "list_detection_prepass",
        })
        # Also emit per-item list_formatting issues for LLM/UI consistency
        for item in group.items:
            if item.has_numpr:
                continue
            issues.append({
                "issue_id": f"{issue_prefix}_item_{item.index}",
                "paragraph_id": item.paragraph_id,
                "function": "formatting",
                "category": "Formatting",
                "type": "list_formatting",
                "severity": "minor",
                "reason": (
                    f"Paragraph belongs to a '{group.detection}' list group "
                    f"with siblings {sibling_ids}; convert to a list item."
                ),
                "suggestion": (
                    f"Convert this paragraph into a bulleted list item, "
                    f"grouped with paragraph_ids {sibling_ids}"
                ),
                "original": item.text,
                "para_indices": para_indices,
                "list_detection": group.detection,
                "source": "list_detection_prepass",
            })
    return issues


def build_list_hint_payload(groups: Sequence[ListGroup]) -> List[Dict[str, Any]]:
    """Compact hint objects injected into the LLM formatting prompt."""
    hints = []
    for g in groups:
        hints.append({
            "detection": g.detection,
            "paragraph_ids": g.paragraph_ids,
            "trigger": g.trigger_text or None,
            "preview": [i.text[:80] for i in g.items[:4]],
            "instruction": (
                "These paragraphs are ALREADY confirmed as one list by the "
                "deterministic pre-pass. Do NOT re-decide whether they are a "
                "list — only confirm and ensure each is flagged as "
                "list_formatting if still plain paragraphs."
            ),
        })
    return hints


def find_unconverted_parallel_runs(
    blocks: Sequence[Any],
    *,
    min_run: int = 3,
    treated_as_list_indices: Optional[Iterable[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Aggregator self-check: flag runs of 3+ consecutive paragraphs sharing an
    opening grammatical pattern that were NOT converted to a list.
    """
    treated = set(treated_as_list_indices or [])
    normalized = [_normalize_block(b, i) for i, b in enumerate(blocks)]
    flags: List[Dict[str, Any]] = []

    i = 0
    n = len(normalized)
    while i < n:
        text = normalized[i]["text"]
        sig = _opening_signature(text) if text else None
        if sig is None:
            i += 1
            continue

        run = [normalized[i]]
        j = i + 1
        while j < n:
            nxt = normalized[j]
            if not nxt["text"]:
                j += 1
                continue
            if _opening_signature(nxt["text"]) != sig:
                break
            run.append(nxt)
            j += 1

        if len(run) >= min_run:
            indices = [r["index"] for r in run]
            already = all(
                r["has_numpr"] or r["index"] in treated or "list" in (r["style"] or "").lower()
                for r in run
            )
            if not already:
                flags.append({
                    "type": "unconverted_parallel_list",
                    "pattern": sig,
                    "indices": indices,
                    "paragraph_ids": [r["paragraph_id"] for r in run],
                    "preview": [r["text"][:60] for r in run[:3]],
                    "count": len(run),
                    "source": "aggregator_list_validation",
                    "needs_review": True,
                    "reason": (
                        f"{len(run)} consecutive paragraphs share '{sig}' "
                        f"openings but were not converted to a Word list."
                    ),
                })
        i = max(j, i + 1)

    return flags


def validate_list_coverage(
    blocks: Sequence[Any],
    detected_groups: Sequence[ListGroup],
    *,
    min_run: int = 3,
) -> List[Dict[str, Any]]:
    """
    Compare structural parallel runs against groups that were detected /
    marked for conversion. Returns leftover flags for manual review.
    """
    covered: set = set()
    for g in detected_groups:
        covered.update(g.indices)
    return find_unconverted_parallel_runs(
        blocks,
        min_run=min_run,
        treated_as_list_indices=covered,
    )
