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
  d) heading_context: a heading whose title names a list-like section
     ("Assumptions", "Constraints", "Objectives", ...) followed by 3+ short
     single-sentence paragraphs up to the next heading.
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
# Heading number a previous export put in front of an objective item:
# "1.4. To provide Google Drive integration ..." -> "To provide ..."
_STALE_HEADING_NUMBER_ON_ITEM_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+(?=To\s+[a-z]+\b)", re.IGNORECASE)

# Detections trusted enough to auto-create issues and auto-apply bullets
# (formatting pre-pass, reformatter export, bulk-fix endpoint). Their members are
# also protected from heading promotion. label_colon stays candidate-only.
HIGH_CONFIDENCE_DETECTIONS = frozenset({
    "infinitive",
    "gerund",
    "trigger_line",
    "trigger_follower",
    "marker",
    "bullet_marker",
    "heading_context",
})

# Section titles whose body is normally a list of short statements.
# Matched case-insensitively against the heading text with numbering removed;
# compound titles ("Assumptions & Constraints") match when every part is listed.
LIST_CONTEXT_HEADINGS = frozenset({
    "assumptions", "constraints", "limitations", "delimitations",
    "scope", "in scope", "out of scope", "project scope",
    "dependencies", "risks", "risk factors",
    "requirements", "functional requirements", "non-functional requirements",
    "non functional requirements",
    "objectives", "specific objectives", "general objectives", "project objectives",
    "aims", "aims and objectives", "goals", "project goals",
    "deliverables", "project deliverables",
    "features", "key features", "main features", "system features",
    "recommendations", "future work", "future enhancements", "future scope",
    "contributions", "benefits", "advantages", "disadvantages",
})
# heading_context items: short, complete single sentences
HEADING_CONTEXT_MAX_WORDS = 45
HEADING_CONTEXT_MIN_ITEMS = 3


def _is_objective_item(text: str) -> bool:
    """'To <verb> ...' with >= 6 words — always a list item, never a heading
    (same threshold as heading_analysis._is_hard_negative_heading)."""
    t = _STALE_HEADING_NUMBER_ON_ITEM_RE.sub("", (text or "").strip(), count=1)
    return bool(_INFINITIVE_RE.match(t)) and len(t.split()) >= 6


def strip_stale_item_number(text: str) -> str:
    """Remove a heading number wrongly typed in front of an objective item."""
    return _STALE_HEADING_NUMBER_ON_ITEM_RE.sub("", (text or "").strip(), count=1)


def is_list_context_heading(text: str) -> bool:
    """True when a heading title names a list-like section (see LIST_CONTEXT_HEADINGS)."""
    t = re.sub(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.|chapter\s+\d+[:.]?)\s+", "", text or "", flags=re.I)
    t = re.sub(r"[:.\s]+$", "", t).strip().lower()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return False
    if t in LIST_CONTEXT_HEADINGS:
        return True
    parts = [p.strip() for p in re.split(r"\s*(?:&|/|,|\band\b)\s*", t) if p.strip()]
    return len(parts) > 1 and all(p in LIST_CONTEXT_HEADINGS for p in parts)


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
    # Objective items ("To provide ...") are list body even when an earlier step
    # wrongly gave them a Heading style — check before trusting the style.
    if _is_objective_item(text):
        return False
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
        text = strip_stale_item_number(str(raw.get("text") or ""))
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
            # image / table sits at (or right before) this paragraph
            "breaks_list": bool(raw.get("breaks_list")),
        }

    # ParagraphBlock-like object
    text = strip_stale_item_number(str(getattr(raw, "text", "") or ""))
    pid = str(getattr(raw, "paragraph_id", "") or f"p{fallback_index}")
    style = str(getattr(raw, "style_name", None) or getattr(raw, "style", "") or "")
    return {
        "index": fallback_index,
        "paragraph_id": pid,
        "text": text,
        "style": style,
         "has_numpr": bool(getattr(raw, "has_numpr", False)) or style.lower().startswith("list"),
        "known_heading": bool(style and _HEADING_STYLE_RE.search(style)),
        "breaks_list": False,
    }


def _collect_heading_context_items(
    normalized: List[Dict[str, Any]],
    start: int,
) -> Tuple[List[ListItem], int]:
    """Items after a list-context heading: short single sentences until the next
    heading. Returns (items, next_scan_index). Empty items = rule did not fire."""
    items: List[ListItem] = []
    j = start
    n = len(normalized)
    while j < n:
        nxt = normalized[j]
        if nxt.get("breaks_list"):
            break
        t = nxt["text"]
        if not t:
            j += 1
            continue
        if _is_heading_like(t, nxt["style"], known_heading=nxt["known_heading"]):
            break
        if _is_trigger_line(t):
            break  # a trigger line starts its own list group
        wc = _word_count(t)
        # Short, complete statement ("Users are assumed to ...").  A label-like line
        # without end punctuation is probably a sub-heading -> stop.
        if wc < 3 or wc > HEADING_CONTEXT_MAX_WORDS or not re.search(r"[.!?;]\s*$", t):
            break
        # more than one sentence -> prose paragraph, not a list item
        if len(re.findall(r"[.!?](?:\s+[A-Z])", t)) >= 1:
            break
        items.append(ListItem(
            index=nxt["index"],
            paragraph_id=nxt["paragraph_id"],
            text=t,
            pattern="heading_context",
            has_numpr=nxt["has_numpr"],
        ))
        j += 1
    return items, j


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
            # ── Signal (d): list-context heading → short single sentences ───
            if is_list_context_heading(text):
                items, j = _collect_heading_context_items(normalized, i + 1)
                # Only claim the section when EVERY body paragraph up to the next
                # heading qualified; otherwise leave it to the other signals.
                reached_end = j >= n or normalized[j].get("breaks_list") or (
                    _is_heading_like(
                        normalized[j]["text"], normalized[j]["style"],
                        known_heading=normalized[j]["known_heading"],
                    )
                    if normalized[j]["text"] else False
                )
                if len(items) >= max(min_items, HEADING_CONTEXT_MIN_ITEMS) and reached_end:
                    groups.append(ListGroup(
                        items=items,
                        trigger_index=block["index"],
                        trigger_text=text,
                        detection="heading_context",
                    ))
                    i = j
                    continue
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


def drop_isolated_list_targets(
    blocks: Sequence[Any],
    target_indices: Iterable[int],
) -> Tuple[List[int], List[int]]:
    """
    A list needs at least two items. Keep a bullet target only when the previous
    or next non-empty paragraph is also a target or already a real list item.
    A single paragraph between two headings ("2.2.3. Organization ..." →
    "Administrative User. Manage ..." → "2.2.4. ...") is body text, not a list.

    Returns (kept, dropped) as sorted paragraph indices.
    """
    targets = set(int(i) for i in target_indices)
    normalized = [_normalize_block(b, i) for i, b in enumerate(blocks)]
    order = [b for b in normalized if b["text"]]
    pos = {b["index"]: k for k, b in enumerate(order)}

    def _listish(k: int) -> bool:
        if k < 0 or k >= len(order):
            return False
        b = order[k]
        # A heading is never bulleted, so a heading target is not a list neighbour
        # ("2.2.3. Organization ..." between two single paragraphs).
        if _is_heading_like(b["text"], b["style"], known_heading=b["known_heading"]):
            return False
        return b["index"] in targets or bool(b["has_numpr"])

    kept, dropped = [], []
    for idx in sorted(targets):
        k = pos.get(idx)
        if k is None:  # empty / unknown paragraph: let the applier decide
            kept.append(idx)
        elif _listish(k - 1) or _listish(k + 1):
            kept.append(idx)
        else:
            dropped.append(idx)
    return kept, dropped


def high_confidence_groups(groups: Sequence[ListGroup]) -> List[ListGroup]:
    return [g for g in groups if (g.detection or "").lower() in HIGH_CONFIDENCE_DETECTIONS]


def protected_list_indices(blocks: Sequence[Any]) -> set:
    """Indices of paragraphs that belong to a high-confidence list group.
    Heading promotion (reformatter, heading fixes) must never touch them."""
    return {
        item.index
        for g in high_confidence_groups(detect_list_groups(blocks))
        for item in g.items
    }


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
            # texts travel with the indices so the applier can re-find the items
            # if the working copy's paragraph indices moved since analysis
            "fix_details": {
                "para_indices": para_indices,
                "texts": [item.text for item in group.items],
            },
            "list_texts": [item.text for item in group.items],
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
