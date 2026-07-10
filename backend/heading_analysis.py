"""
heading_analysis.py — Deterministic heading detection, template matching, and level assignment.

For each document block:
  1. Detect whether the block is a heading.
  2. Match detected headings against the template outline (with synonyms).
  3. Assign heading levels from the template or inferred from numbering/sequence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from models import DocumentModel

# ── Synonym groups for template matching ─────────────────────────────────────

_SYNONYM_GROUPS: List[set[str]] = [
    {"background", "context", "overview", "setting", "problem statement"},
    {"literature review", "related work", "related studies", "prior research", "state of the art"},
    {"methodology", "methods", "materials and methods", "research design", "approach"},
    {"results", "findings", "data analysis", "analysis"},
    {"discussion", "interpretation"},
    {"conclusion", "conclusions", "summary", "closing remarks"},
    {"introduction", "intro"},
    {"abstract", "executive summary", "summary"},
    {"references", "bibliography", "works cited"},
    {"acknowledgements", "acknowledgments", "acknowledgement"},
    {"table of contents", "contents"},
    {"title page", "cover page"},
    {"recommendations", "suggestions"},
    {"declaration", "certification"},
]

_CAPTION_RE = re.compile(
    r"^(figure|fig\.?|table|tab\.?|image|chart|diagram|equation|eq\.?)\s*[\d.:]+",
    re.IGNORECASE,
)
_NUMBERING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
_LIST_ITEM_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219•\-*–·]\s+")
_ROMAN_RE = re.compile(r"^[IVXLC]+\.\s+", re.IGNORECASE)
_COMMON_SECTION_RE = re.compile(
    r"^(introduction|abstract|methodology|methods|results|findings|discussion|"
    r"conclusion|conclusions|references|bibliography|acknowledgements|acknowledgments|"
    r"appendix|literature review|related work|background|executive summary|"
    r"recommendations|declaration|table of contents)(?:\s|$)",
    re.IGNORECASE,
)
_LABEL_SUFFIX_RE = re.compile(r"[:]\s*$|(?:\s|(?<=\w))[-–—]\s*$")
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were",
    "with", "we", "they", "these", "those",
})


@dataclass
class TemplateEntry:
    name: str
    level: int
    parent: Optional[str]
    order: int


@dataclass
class AnalysisBlock:
    block_id: int
    text: str
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    style_name: Optional[str] = None
    numbering_prefix: Optional[str] = None
    prev_blank: bool = False
    next_blank: bool = False
    paragraph_id: str = ""


@dataclass
class MatchContext:
    last_matched_h1: Optional[str] = None
    last_matched_h2: Optional[str] = None
    last_matched_h3: Optional[str] = None


def _normalize(text: str) -> str:
    cleaned = (text or "").strip().rstrip(":").strip()
    cleaned = re.sub(r"^[\d]+(?:\.[\d]+)*\.?\s+", "", cleaned).strip()
    cleaned = re.sub(r"^[IVXLC]+\.\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.lower()


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _extract_numbering_prefix(text: str) -> Tuple[Optional[str], str]:
    match = _NUMBERING_RE.match((text or "").strip())
    if not match:
        return None, (text or "").strip()
    return match.group(1), match.group(2).strip()


def _numbering_depth(prefix: Optional[str]) -> Optional[int]:
    if not prefix:
        return None
    return min(4, max(1, prefix.count(".") + 1))


def _level_label(level: int) -> str:
    return f"h{max(1, min(4, level))}"


def _synonym_match(a: str, b: str) -> bool:
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        if len(longer) <= len(shorter) + 8:
            return True
    for group in _SYNONYM_GROUPS:
        if na in group and nb in group:
            return True
    return False


def _text_match_score(text: str, template_name: str) -> float:
    norm_text = _normalize(text)
    norm_name = _normalize(template_name)
    if not norm_text or not norm_name:
        return 0.0
    if norm_text == norm_name:
        return 1.0
    if _synonym_match(norm_text, norm_name):
        return 0.9
    if norm_text.endswith(f" {norm_name}") or norm_name in norm_text:
        if len(norm_text) <= len(norm_name) + 10:
            return 0.85
    # Token overlap for partial matches
    text_tokens = set(norm_text.split())
    name_tokens = set(norm_name.split())
    if name_tokens and name_tokens.issubset(text_tokens):
        return 0.75
    overlap = len(text_tokens & name_tokens)
    if overlap and overlap >= max(1, len(name_tokens) - 1):
        return 0.65
    return 0.0


def build_template_outline(required_sections: List[Any]) -> List[TemplateEntry]:
    """Build a flat template outline with parent links from required_sections."""
    entries: List[TemplateEntry] = []
    parent_stack: Dict[int, Optional[str]] = {0: None, 1: None, 2: None, 3: None}

    for idx, sec in enumerate(required_sections or []):
        if isinstance(sec, str):
            name = sec.strip()
            level = 1
        elif isinstance(sec, dict):
            name = str(sec.get("name") or "").strip()
            level = int(sec.get("heading_level") or sec.get("headingLevel") or 1)
        else:
            continue
        if not name:
            continue

        level = max(1, min(4, level))
        parent = parent_stack.get(level - 1)
        entries.append(TemplateEntry(name=name, level=level, parent=parent, order=idx + 1))
        parent_stack[level] = name
        for deeper in range(level + 1, 5):
            parent_stack[deeper] = None

    return entries


def blocks_from_document(doc: DocumentModel) -> List[AnalysisBlock]:
    """Convert parsed paragraphs into analysis blocks with metadata."""
    blocks: List[AnalysisBlock] = []
    for idx, para in enumerate(doc.paragraphs):
        prefix = para.numbering_prefix
        if prefix is None:
            prefix, _ = _extract_numbering_prefix(para.text)

        style_name = para.style_name or para.style
        blocks.append(
            AnalysisBlock(
                block_id=idx,
                text=para.text,
                font_size=para.font_size,
                bold=para.bold,
                style_name=style_name,
                numbering_prefix=prefix,
                prev_blank=para.prev_blank,
                next_blank=para.next_blank,
                paragraph_id=para.paragraph_id,
            )
        )
    return blocks


def blocks_from_dicts(raw_blocks: List[Dict[str, Any]]) -> List[AnalysisBlock]:
    """Convert API-style block dicts into AnalysisBlock objects."""
    blocks: List[AnalysisBlock] = []
    for idx, raw in enumerate(raw_blocks):
        text = str(raw.get("text") or "").strip()
        prefix = raw.get("numbering_prefix")
        if prefix is None:
            prefix, _ = _extract_numbering_prefix(text)
        blocks.append(
            AnalysisBlock(
                block_id=int(raw.get("block_id", idx)),
                text=text,
                font_size=raw.get("font_size"),
                bold=raw.get("bold"),
                style_name=raw.get("style_name") or raw.get("style"),
                numbering_prefix=prefix,
                prev_blank=bool(raw.get("prev_blank")),
                next_blank=bool(raw.get("next_blank")),
                paragraph_id=str(raw.get("paragraph_id") or ""),
            )
        )
    return blocks


def _is_heading_style(style_name: Optional[str]) -> Optional[int]:
    if not style_name:
        return None
    low = style_name.lower()
    for lvl in (1, 2, 3, 4):
        if f"heading {lvl}" in low or f"heading{lvl}" in low:
            return lvl
    if "title" in low:
        return 1
    if "subtitle" in low:
        return 2
    return None


def detect_heading(block: AnalysisBlock) -> Tuple[bool, float]:
    """Step 1 — decide if a block is a heading."""
    text = (block.text or "").strip()
    if not text:
        return False, 0.0

    if _CAPTION_RE.match(text):
        return False, 0.05
    if _LIST_ITEM_RE.match(text):
        return False, 0.1

    score = 0.0
    signals = 0

    style_level = _is_heading_style(block.style_name)
    if style_level is not None:
        score += 0.55
        signals += 2

    if block.bold and block.font_size is not None:
        if block.font_size >= 14:
            score += 0.35
            signals += 2
        elif block.font_size >= 12:
            score += 0.2
            signals += 1

    words = _word_count(text)
    ends_sentence = text.rstrip().endswith((".", "?", "!"))
    _, body = _extract_numbering_prefix(text)
    body_words = _word_count(body or text)

    if block.numbering_prefix and body_words <= 12 and not (body or text).rstrip().endswith("."):
        score += 0.35
        signals += 2

    norm_body = _normalize(body or text)
    if _COMMON_SECTION_RE.match(norm_body):
        score += 0.4
        signals += 2

    if words <= 10:
        score += 0.1
    else:
        score -= 0.15

    if not ends_sentence:
        score += 0.12
        signals += 1
    else:
        score -= 0.2

    if block.prev_blank:
        score += 0.12
        signals += 1
    if block.next_blank:
        score += 0.1
        signals += 1

    if text.isupper() and 1 <= words <= 8:
        score += 0.15
        signals += 1
    elif text.istitle() and body_words <= 10 and not ends_sentence:
        score += 0.1
        signals += 1

    # Short alone is not enough — require at least two supporting signals unless
    # style metadata or section numbering is present.
    if signals < 2 and style_level is None and not block.numbering_prefix:
        score = min(score, 0.45)

    confidence = max(0.0, min(1.0, score))
    return confidence >= 0.5, round(confidence, 3)


def _ends_with_label_punctuation(text: str) -> bool:
    """Trailing colon or dash marks a label, not a standalone sub-heading."""
    return bool(_LABEL_SUFFIX_RE.search((text or "").strip()))


def _is_bullet_or_list(text: str) -> bool:
    stripped = (text or "").strip()
    if _LIST_ITEM_RE.match(stripped):
        return True
    return bool(re.match(r"^\d+[\.\)]\s+\S", stripped))


def _has_substantive_words(text: str) -> bool:
    words = re.findall(r"\S+", text or "")
    content = [w for w in words if w.lower().strip(".,;:") not in _STOPWORDS]
    return len(content) >= 1


def _is_body_like(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if _word_count(stripped) >= 12:
        return True
    return stripped.endswith((".", "?", "!"))


def _infer_block_heading_level(block: AnalysisBlock, row: Dict[str, Any]) -> Optional[int]:
    """Best-effort heading level for a block before full level assignment."""
    existing = _level_to_int(row.get("level"))
    if existing is not None:
        return existing

    depth = _numbering_depth(block.numbering_prefix)
    if depth is not None:
        return depth

    style_level = _is_heading_style(block.style_name)
    if style_level is not None:
        return style_level

    if row.get("is_heading"):
        return 1
    return None


def detect_unnumbered_subheading(
    block: AnalysisBlock,
    blocks: List[AnalysisBlock],
    idx: int,
    results: List[Dict[str, Any]],
) -> Tuple[bool, float, Optional[int]]:
    """
    Detect standalone unnumbered sub-headings by document position.

    Pattern: numbered/parent heading → short unnumbered line → body paragraph or bullets.
    """
    text = (block.text or "").strip()
    if not text:
        return False, 0.0, None

    if block.numbering_prefix or _LIST_ITEM_RE.match(text) or _CAPTION_RE.match(text):
        return False, 0.0, None

    words = _word_count(text)
    if words < 1 or words > 4:
        return False, 0.0, None

    if text.rstrip().endswith((".", "?", "!")):
        return False, 0.0, None

    if _ends_with_label_punctuation(text):
        return False, 0.0, None

    if not _has_substantive_words(text):
        return False, 0.0, None

    if not (text.istitle() or text.isupper() or (words == 1 and text[0].isupper())):
        return False, 0.0, None

    if idx == 0 or idx >= len(blocks) - 1:
        return False, 0.0, None

    prev_block = blocks[idx - 1]
    prev_row = results[idx - 1]
    prev_level = _infer_block_heading_level(prev_block, prev_row)
    prev_is_heading = bool(prev_row.get("is_heading"))
    prev_is_numbered = bool(prev_block.numbering_prefix)

    if not prev_is_heading and not prev_is_numbered:
        return False, 0.0, None

    if prev_level is None:
        prev_level = 1

    next_text = (blocks[idx + 1].text or "").strip()
    if not next_text:
        return False, 0.0, None

    next_is_body = _is_body_like(next_text)
    next_is_list = _is_bullet_or_list(next_text)
    if not next_is_body and not next_is_list:
        return False, 0.0, None

    # Avoid promoting when the next block is another short title-like line.
    if (
        not next_is_body
        and _word_count(next_text) <= 4
        and not _is_bullet_or_list(next_text)
    ):
        return False, 0.0, None

    # Already a numbered heading — not an unnumbered sub-heading.
    if results[idx].get("is_heading") and block.numbering_prefix:
        return False, 0.0, None

    score = 0.72
    if prev_is_numbered:
        score += 0.12
    if next_is_body:
        score += 0.08
    if next_is_list:
        score += 0.06
    if block.prev_blank or prev_block.next_blank:
        score += 0.04

    return True, round(min(1.0, score), 3), prev_level


def _detect_unnumbered_subheadings(
    blocks: List[AnalysisBlock],
    results: List[Dict[str, Any]],
    heading_indices: List[int],
) -> None:
    """Pass 1b — promote or reclassify contextual unnumbered sub-headings."""
    for idx, block in enumerate(blocks):
        is_sub, confidence, parent_level = detect_unnumbered_subheading(
            block, blocks, idx, results,
        )
        if not is_sub or parent_level is None:
            continue

        child_level = min(4, parent_level + 1)
        already_heading = bool(results[idx].get("is_heading"))

        results[idx].update({
            "is_heading": True,
            "detection_confidence": max(
                float(results[idx].get("detection_confidence") or 0),
                confidence,
            ),
            "level": _level_label(child_level),
            "heading_kind": "unnumbered_subheading",
            "parent_level": parent_level,
            "matched_template_heading": None,
            "match_confidence": None,
        })
        if not already_heading:
            results[idx]["detection_confidence"] = confidence
        if idx not in heading_indices:
            heading_indices.append(idx)

    heading_indices.sort()


def _parent_matches(context: MatchContext, entry: TemplateEntry) -> bool:
    if entry.level == 1 or not entry.parent:
        return True
    if entry.level == 2:
        actual = context.last_matched_h1
    elif entry.level == 3:
        actual = context.last_matched_h2
    else:
        actual = context.last_matched_h3
    if not actual:
        return True
    return _synonym_match(actual, entry.parent)


def match_template_heading(
    text: str,
    template: List[TemplateEntry],
    context: MatchContext,
) -> Tuple[Optional[str], float]:
    """Step 2 — match heading text to a template entry."""
    best_name: Optional[str] = None
    best_score = 0.0

    for entry in template:
        base = _text_match_score(text, entry.name)
        if base < 0.65:
            continue
        if not _parent_matches(context, entry):
            base *= 0.35
        if entry.level == 1:
            base = min(1.0, base + 0.05)
        if base > best_score:
            best_score = base
            best_name = entry.name

    if best_score < 0.65:
        return None, None
    return best_name, round(best_score, 3)


def _update_match_context(context: MatchContext, matched_name: str, level: int) -> None:
    if level == 1:
        context.last_matched_h1 = matched_name
        context.last_matched_h2 = None
        context.last_matched_h3 = None
    elif level == 2:
        context.last_matched_h2 = matched_name
        context.last_matched_h3 = None
    elif level == 3:
        context.last_matched_h3 = matched_name


def _template_level_for_name(name: str, template: List[TemplateEntry]) -> int:
    for entry in template:
        if _synonym_match(entry.name, name):
            return entry.level
    return 1


def _infer_levels_from_sequence(
    heading_indices: List[int],
    blocks: List[AnalysisBlock],
    results: List[Dict[str, Any]],
) -> None:
    """Step 3b — infer levels for unmatched headings using document sequence."""
    current = 1

    for idx in heading_indices:
        row = results[idx]
        if row.get("level"):
            current = _level_to_int(row["level"]) or current
            continue

        if row.get("matched_template_heading") is not None:
            current = int(row["level"][1])
            continue

        block = blocks[idx]
        depth = _numbering_depth(block.numbering_prefix)
        if depth is not None:
            row["level"] = _level_label(depth)
            row["detection_confidence"] = row["detection_confidence"]
            current = depth
            continue

        text = block.text
        words = _word_count(text)
        if words <= 4:
            level = min(4, current + 1)
        elif current == 1:
            level = 1
        else:
            level = min(4, current + 1)

        row["level"] = _level_label(level)
        current = level


def analyze_headings(
    blocks: List[AnalysisBlock],
    template: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Run heading detection, template matching, and level assignment for all blocks.

    Returns one result dict per block in the same order as the input.
    """
    outline = build_template_outline((template or {}).get("required_sections", []))

    results: List[Dict[str, Any]] = []
    heading_indices: List[int] = []
    context = MatchContext()

    # Pass 1 — detection
    for block in blocks:
        is_heading, det_conf = detect_heading(block)
        row: Dict[str, Any] = {
            "block_id": block.block_id,
            "is_heading": is_heading,
            "matched_template_heading": None,
            "level": None,
            "detection_confidence": det_conf if is_heading else round(det_conf, 3),
            "match_confidence": None,
            "heading_kind": "standard" if is_heading else None,
        }
        if not is_heading:
            row["detection_confidence"] = round(1.0 - det_conf, 3)
            row["matched_template_heading"] = None
            row["level"] = None
            row["match_confidence"] = None
        else:
            heading_indices.append(len(results))
        results.append(row)

    # Pass 1b — unnumbered sub-headings (e.g. "Architecture" under "3. Methodology")
    _detect_unnumbered_subheadings(blocks, results, heading_indices)

    # Pass 2 — template matching (document order; skip pre-leveled sub-headings)
    for idx in heading_indices:
        block = blocks[idx]
        if results[idx].get("heading_kind") == "unnumbered_subheading":
            continue
        matched, match_conf = match_template_heading(block.text, outline, context)
        results[idx]["matched_template_heading"] = matched
        results[idx]["match_confidence"] = match_conf

        if matched:
            level = _template_level_for_name(matched, outline)
            entry = next((e for e in outline if e.name == matched), None)
            if entry:
                level = entry.level
            results[idx]["level"] = _level_label(level)
            _update_match_context(context, matched, level)
        else:
            depth = _numbering_depth(block.numbering_prefix)
            if depth is not None:
                results[idx]["level"] = _level_label(depth)

    # Pass 3 — infer levels for remaining unmatched headings
    _infer_levels_from_sequence(heading_indices, blocks, results)

    return results


def analyze_document_headings(
    doc: DocumentModel,
    template: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Analyze all paragraphs in a DocumentModel and enrich results for the API."""
    blocks = blocks_from_document(doc)
    raw = analyze_headings(blocks, template)

    enriched: List[Dict[str, Any]] = []
    for block, row in zip(blocks, raw):
        item = dict(row)
        item["paragraph_id"] = block.paragraph_id
        item["text"] = block.text
        enriched.append(item)
    return enriched


def _level_to_int(level: Optional[str]) -> Optional[int]:
    if not level or not str(level).lower().startswith("h"):
        return None
    try:
        return max(1, min(4, int(str(level)[1])))
    except (TypeError, ValueError):
        return None


def enrich_matches_with_fix_status(
    matches: List[Dict[str, Any]],
    document_blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Add fix metadata by comparing detected headings against preview blocks."""
    blocks_by_pid = {
        b.get("paragraph_id"): b
        for b in document_blocks
        if b.get("paragraph_id")
    }

    enriched: List[Dict[str, Any]] = []
    for match in matches:
        row = dict(match)
        if not row.get("is_heading"):
            row["fix_status"] = None
            row["fix_needed"] = False
            enriched.append(row)
            continue

        pid = row.get("paragraph_id", "")
        block = blocks_by_pid.get(pid, {})
        expected_level = _level_to_int(row.get("level"))
        current_type = (block.get("type") or "paragraph").lower()
        current_level = block.get("level")
        current_style = block.get("style") or "Normal"
        matched_name = row.get("matched_template_heading")

        fix_needed = False
        fix_status = "ok"
        fix_description = ""

        if expected_level is None:
            fix_status = "unknown_level"
            fix_description = "Heading level could not be determined."
        elif current_type != "heading":
            fix_status = "needs_style"
            fix_needed = True
            suffix = f' for "{matched_name}"' if matched_name else ""
            fix_description = f"Apply Heading {expected_level} style{suffix}."
        elif current_level != expected_level:
            fix_status = "wrong_level"
            fix_needed = True
            suffix = f' (template: "{matched_name}")' if matched_name else ""
            fix_description = (
                f"Change from Heading {current_level} to Heading {expected_level}{suffix}."
            )
        elif matched_name is None:
            fix_status = "unmatched"
            if row.get("heading_kind") == "unnumbered_subheading":
                fix_description = (
                    f"Unnumbered sub-heading \"{row.get('text', '')}\" "
                    f"should use Heading {expected_level} style."
                )
            else:
                fix_description = (
                    f"Heading \"{row.get('text', '')}\" is not in the template outline."
                )
        else:
            fix_description = f"Matches template section \"{matched_name}\" at H{expected_level}."

        row.update({
            "fix_status": fix_status,
            "fix_needed": fix_needed,
            "fix_description": fix_description,
            "expected_level": expected_level,
            "current_type": current_type,
            "current_level": current_level,
            "current_style": current_style,
            "status": "ok" if not fix_needed else fix_status,
        })
        enriched.append(row)

    return enriched


def heading_matches_to_issues(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert fixable heading matches into formatting issues for the issues pipeline."""
    issues: List[Dict[str, Any]] = []
    for match in matches:
        if not match.get("is_heading") or not match.get("fix_needed"):
            continue

        pid = match.get("paragraph_id", "")
        level = match.get("expected_level") or 1
        text = match.get("text", "")
        matched = match.get("matched_template_heading")
        fix_status = match.get("fix_status", "needs_style")

        if fix_status == "wrong_level":
            reason = (
                f"Heading \"{text}\" uses Heading {match.get('current_level')} "
                f"but should be Heading {level}."
            )
            suggestion = f"Apply Heading {level} style"
        else:
            match_suffix = f' matching "{matched}"' if matched else ""
            reason = (
                f"\"{text}\" is detected as a section heading{match_suffix} "
                f"but does not use Word Heading {level} style."
            )
            suggestion = f"Apply Heading {level} style"

        issues.append({
            "function": "formatting",
            "category": "Formatting",
            "type": "heading_style",
            "severity": "major",
            "paragraph_id": pid,
            "page": 0,
            "reason": reason,
            "description": match.get("fix_description") or reason,
            "suggestion": suggestion,
            "original": text,
            "current": text,
            "heading_level": level,
            "matched_template_heading": matched,
            "issue_id": f"heading_match_{pid}",
            "source": "template_heading_analysis",
        })

    return issues
