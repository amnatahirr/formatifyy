"""
heading_analysis.py — Heading detection, template matching, and level assignment.

Architecture (Claude-first when LLM candidates are provided)
-----------------------------------------------------------
  0. CLAUDE PASS — Structure detection via LLM (see functions/heading_detect.py).
     Candidates are seeded as headings first.

  PASS A — Template soft-matching (cross-check):
      Match paragraph text against required_sections (synonyms/abbreviations).
      Each template entry can be claimed ONCE (so duplicate names such as
      Introduction H1 / Introduction H2 resolve in document order).
      Matched headings get the template level and source="matched".

  RULE CROSS-CHECK — Hard negatives (captions, list items, "2) foo" items,
      runs of "1. 2. 3." lines, long body sentences) reject false Claude
      positives. Deterministic detect_heading() recovers clear headings
      Claude may have missed.

  PASS B — Structural inference for unnumbered sub-headings Claude missed
      (source="inferred").

  COMPOUND PARTS — template entry "A & B" (H2): separate lines "A" / "B"
      under it become children (H3), not sibling H2s.

  CLAUDE-ONLY extras — Claude headings that do not match the template are
      marked source="claude_only" and require a user Keep/Discard decision
      before style apply.

  When claude_candidates is None, behaviour falls back to the deterministic
  Pass A/B pipeline (used by reformatter / unit tests).

  Missing template headings → source="missing".

  heading_plan_from_matches() turns the final decisions into the single plan
  that the exporter (reformatter) must follow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from models import DocumentModel

# ── Synonym groups for template matching ─────────────────────────────────────

_SYNONYM_GROUPS: List[set[str]] = [
    {"background", "context", "overview", "setting"},
    {"problem statement", "problem"},
    {"literature review", "related work", "related studies", "prior research", "state of the art"},
    {"methodology", "methods", "materials and methods", "research design", "approach"},
    {"results", "findings", "data analysis"},
    {"discussion", "interpretation"},
    {"conclusion", "conclusions", "closing remarks"},
    {"introduction", "intro"},
    {"abstract", "executive summary"},
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

# ── Typed prefixes / list-item patterns ──────────────────────────────────────
# Matches ONE leading typed marker: "1.", "1.2.3", "2)", "(2)", "(a)", "a)", "IV."
_TYPED_PREFIX_RE = re.compile(
    r"^\s*(?:\(?\d+(?:\.\d+)*[.)]?\)?|[IVXLC]+\.|\(?[a-zA-Z]\))\s+"
)
# "2) System Design", "(a) Foo", "b) Foo" -> list item, never a heading
_PAREN_LIST_RE = re.compile(r"^\s*(?:\(?\d+\)|\(?[a-zA-Z]\))\s+\S")
# "1. foo", "2) foo" used for consecutive-run detection
_DOT_NUM_RE = re.compile(r"^\s*(\d+)[.)]\s+\S")
# "2. 2) System Design" / "3.1.1. 5) Deployment" -> an old export put a heading
# number in front of a list item.
_DOUBLE_PREFIX_RE = re.compile(
    r"^\s*\d+(?:\.\d+)*\.?\s+(?:\d+\)|\(?[a-zA-Z]\))\s+\S"
)


def strip_typed_prefixes(text: str) -> str:
    """'3.1.1. 5) Deployment' -> 'Deployment' (loops until no prefix is left)."""
    t = (text or "").strip().rstrip(":").strip()
    for _ in range(4):
        n = _TYPED_PREFIX_RE.sub("", t, count=1).strip()
        if not n or n == t:
            break
        t = n
    return t


def _looks_like_typed_list_item(text: str) -> bool:
    t = (text or "").strip()
    return bool(_PAREN_LIST_RE.match(t) or _DOUBLE_PREFIX_RE.match(t))


# Front-matter section patterns to exclude from missing-heading detection
_FRONTMATTER_PATTERNS = [
    re.compile(r"^(title\s*page|cover\s*page|title|cover)$", re.I),
    re.compile(r"^(declaration|certification|certificate|undertaking)$", re.I),
    re.compile(r"^(table\s+of\s+contents|contents|toc)$", re.I),
    re.compile(r"^(list\s+of\s+figures|list\s+of\s+images|lof|table\s+of\s+figures)$", re.I),
    re.compile(r"^(list\s+of\s+tables|lot)$", re.I),
    re.compile(r"^(list\s+of\s+(abbreviations|symbols|appendices))$", re.I),
    re.compile(r"^\{\{.*\}\}$", re.I),  # Placeholder-style entries
]


def _is_frontmatter_section(name: str) -> bool:
    """Return True if the section name is a front-matter entry."""
    text = (name or "").strip()
    if not text:
        return True
    for pattern in _FRONTMATTER_PATTERNS:
        if pattern.match(text):
            return True
    return False


@dataclass
class TemplateEntry:
    name: str
    level: int
    parent: Optional[str]
    order: int
    aliases: List[str] = field(default_factory=list)


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
    # Template entries already matched once (an entry is claimed by ONE paragraph)
    claimed_orders: set = field(default_factory=set)
    last_entry: Optional[TemplateEntry] = None


def _normalize(text: str) -> str:
    return strip_typed_prefixes(text).lower()


def missing_heading_issue_id(name: str) -> str:
    """Stable issue_id for a template heading that is missing from the document."""
    return f"missing_heading_{_normalize(str(name or 'section'))}"


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


def _is_zero_based_prefix(prefix: Optional[str]) -> bool:
    """True for broken prefixes like '0', '0.1', '0.1.2' (should not drive level)."""
    if not prefix:
        return False
    return str(prefix).split(".", 1)[0] == "0"


def _reliable_numbering_depth(prefix: Optional[str]) -> Optional[int]:
    """
    Numbering depth for level assignment.
    Ignores zero-based prefixes (0.1 Abstract) which are document bugs, not H2.
    """
    if _is_zero_based_prefix(prefix):
        return None
    return _numbering_depth(prefix)


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


def _content_tokens(text: str) -> set[str]:
    return {
        t for t in (text or "").lower().split()
        if t and t not in _STOPWORDS and len(t) > 1
    }


def _text_match_score(text: str, template_name: str) -> float:
    """
    Soft match score between document heading text and an admin template name.

    Handles abbreviated forms ("Problem" ↔ "Problem Statement") and synonyms.
    Does NOT equate related-but-distinct titles (e.g. "Specific Objectives"
    must not match "Main Objectives" via a shared noun).
    """
    norm_text = _normalize(text)
    norm_name = _normalize(template_name)
    if not norm_text or not norm_name:
        return 0.0
    if norm_text == norm_name:
        return 1.0
    if _synonym_match(norm_text, norm_name):
        return 0.9

    # Containment only when lengths are close (avoids long body sentences)
    if norm_name in norm_text and len(norm_text) <= len(norm_name) + 10:
        return 0.85
    if norm_text in norm_name and len(norm_name) <= len(norm_text) + 12:
        # "Problem" inside "Problem Statement"
        return 0.84

    text_tokens = set(norm_text.split())
    name_tokens = set(norm_name.split())
    text_content = _content_tokens(norm_text)
    name_content = _content_tokens(norm_name)

    # Template tokens fully appear in doc text ("Problem Statement" in longer title)
    if name_tokens and name_tokens.issubset(text_tokens):
        return 0.75

    # Doc text is a shorter form of the template name ("Problem" → "Problem Statement")
    if text_content and name_content and text_content.issubset(name_content):
        coverage = len(text_content) / max(1, len(name_content))
        if coverage >= 0.5:
            return 0.82
        if len(text_content) == 1:
            single = next(iter(text_content))
            if single in {"and", "or", "of", "for", "with", "from", "into", "main"}:
                return 0.0
            return 0.72

    overlap = len(text_tokens & name_tokens)
    content_overlap = len(text_content & name_content)
    if name_content and content_overlap >= len(name_content) and content_overlap >= 2:
        return 0.7
    if (
        content_overlap
        and content_overlap >= max(2, len(name_content) - 1)
        and content_overlap >= max(2, len(text_content) - 1)
    ):
        return 0.68
    if overlap and overlap >= max(2, len(name_tokens) - 0):
        if len(name_tokens) >= 2 and overlap == len(name_tokens):
            return 0.65
    return 0.0


def _compound_parts(name: str) -> List[str]:
    """'Assumptions & Constraints' -> ['Assumptions', 'Constraints']; [] if not compound."""
    parts = [
        p.strip()
        for p in re.split(r"\s*(?:&|/|,|\band\b)\s*", name or "", flags=re.I)
        if p.strip()
    ]
    return parts if len(parts) > 1 else []


def build_template_outline(required_sections: List[Any]) -> List[TemplateEntry]:
    """
    Build a flat template outline with parent links from required_sections.
    Filters out front-matter entries (cover, info, TOC, lists) - only real
    body content headings are considered for missing-heading detection.

    A section dict may carry ``aliases: ["Overview", ...]`` — alternative
    document titles that should match this exact entry.
    """
    entries: List[TemplateEntry] = []
    parent_stack: Dict[int, Optional[str]] = {0: None, 1: None, 2: None, 3: None}
    order_counter = 0

    for idx, sec in enumerate(required_sections or []):
        aliases: List[str] = []
        if isinstance(sec, str):
            name = sec.strip()
            level = 1
        elif isinstance(sec, dict):
            name = str(sec.get("name") or "").strip()
            level = int(sec.get("heading_level") or sec.get("headingLevel") or 1)
            raw_aliases = sec.get("aliases") or []
            if isinstance(raw_aliases, str):
                raw_aliases = [raw_aliases]
            aliases = [str(a).strip() for a in raw_aliases if str(a).strip()]
        else:
            continue
        if not name:
            continue

        # Skip front-matter entries
        if _is_frontmatter_section(name):
            continue

        level = max(1, min(4, level))
        parent = parent_stack.get(level - 1)
        order_counter += 1
        entries.append(
            TemplateEntry(name=name, level=level, parent=parent, order=order_counter, aliases=aliases)
        )
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


def _is_toc_style(block: AnalysisBlock) -> bool:
    low = (block.style_name or "").lower()
    return low.startswith("toc") or "table of contents" in low


def find_numbered_list_runs(blocks: List[AnalysisBlock], min_len: int = 3) -> set[int]:
    """
    Block indices that belong to a run of consecutive short lines numbered
    1. 2. 3. (or 1) 2) 3)) — an SDLC-style list or a typed table of contents,
    never a set of headings. Blank blocks are ignored while scanning.
    """
    idxs = [i for i, b in enumerate(blocks) if (b.text or "").strip()]
    out: set[int] = set()
    k = 0
    while k < len(idxs):
        m = _DOT_NUM_RE.match(blocks[idxs[k]].text)
        if m and int(m.group(1)) == 1:
            j = k + 1
            while j < len(idxs):
                mj = _DOT_NUM_RE.match(blocks[idxs[j]].text)
                if not mj or int(mj.group(1)) != j - k + 1:
                    break
                j += 1
            if j - k >= min_len:
                out.update(idxs[k:j])
            k = max(j, k + 1)
        else:
            k += 1
    return out


def detect_heading(block: AnalysisBlock) -> Tuple[bool, float]:
    """Step 1 — decide if a block is a heading."""
    text = (block.text or "").strip()
    if not text:
        return False, 0.0

    if _CAPTION_RE.match(text):
        return False, 0.05
    if _LIST_ITEM_RE.match(text):
        return False, 0.1
    if _looks_like_typed_list_item(text):
        return False, 0.1
    # Objective-style infinitives are list body, never headings
    if re.match(r"^To\s+[a-z]+\b", text, re.IGNORECASE) and _word_count(text) >= 6:
        return False, 0.05

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
    if re.match(r"^\d+[\.\)]\s+\S", stripped):
        return True
    if _looks_like_typed_list_item(stripped):
        return True
    # Infinitive / gerund goal-style items also read as list bodies under a heading
    if re.match(r"^To\s+[a-z]+\b", stripped, re.IGNORECASE):
        return True
    if re.match(r"^[A-Z][a-z]*ing\b", stripped) and _word_count(stripped) <= 40:
        return True
    return False


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


def _looks_like_section_label(text: str) -> bool:
    """Short, non-sentence line that can serve as a structural sub-heading."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    # Never promote objective infinitives to headings
    if re.match(r"^To\s+[a-z]+\b", stripped, re.IGNORECASE):
        return False
    # Never promote typed list items ("2) System Design")
    if _looks_like_typed_list_item(stripped):
        return False
    words = _word_count(stripped)
    if words < 1 or words > 8:
        return False
    if stripped.endswith((".", "?", "!")):
        return False
    if _ends_with_label_punctuation(stripped):
        return False
    if _LIST_ITEM_RE.match(stripped) or _CAPTION_RE.match(stripped):
        return False
    if not _has_substantive_words(stripped):
        return False
    # Prefer title case / uppercase / short Capitalized phrases
    if stripped.istitle() or stripped.isupper():
        return True
    if stripped[0].isupper() and words <= 5:
        return True
    return False


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


def _nearest_preceding_heading(
    blocks: List[AnalysisBlock],
    results: List[Dict[str, Any]],
    idx: int,
) -> Tuple[Optional[int], Optional[int]]:
    """Return (block_index, level) of the nearest preceding known heading."""
    for prev_idx in range(idx - 1, -1, -1):
        row = results[prev_idx]
        if not row.get("is_heading"):
            continue
        level = _infer_block_heading_level(blocks[prev_idx], row)
        if level is None:
            continue
        return prev_idx, level
    return None, None


def detect_unnumbered_subheading(
    block: AnalysisBlock,
    blocks: List[AnalysisBlock],
    idx: int,
    results: List[Dict[str, Any]],
) -> Tuple[bool, float, Optional[int], Optional[int]]:
    """
    PASS B helper — detect standalone unnumbered sub-headings by structure.

    Returns (is_subheading, confidence, parent_level, parent_idx).
    Pattern: known/numbered heading → short unnumbered label → body paragraph or list.
    """
    text = (block.text or "").strip()
    if not text:
        return False, 0.0, None, None

    # Already matched in Pass A — leave alone
    if results[idx].get("source") == "matched":
        return False, 0.0, None, None

    if block.numbering_prefix or _LIST_ITEM_RE.match(text) or _CAPTION_RE.match(text):
        return False, 0.0, None, None

    if _looks_like_typed_list_item(text):
        return False, 0.0, None, None

    if not _looks_like_section_label(text):
        return False, 0.0, None, None

    if idx == 0 or idx >= len(blocks) - 1:
        return False, 0.0, None, None

    parent_idx, parent_level = _nearest_preceding_heading(blocks, results, idx)
    if parent_idx is None or parent_level is None:
        return False, 0.0, None, None

    parent_block = blocks[parent_idx]
    parent_row = results[parent_idx]
    parent_is_reliable = (
        parent_row.get("source") == "matched"
        or bool(parent_block.numbering_prefix)
        or _is_heading_style(parent_block.style_name) is not None
    )
    if not parent_is_reliable and (idx - parent_idx) > 3:
        return False, 0.0, None, None

    next_text = (blocks[idx + 1].text or "").strip()
    if not next_text:
        return False, 0.0, None, None

    next_is_body = _is_body_like(next_text)
    next_is_list = _is_bullet_or_list(next_text)
    if not next_is_body and not next_is_list:
        return False, 0.0, None, None

    if (
        not next_is_body
        and not next_is_list
        and _word_count(next_text) <= 4
    ):
        return False, 0.0, None, None

    if results[idx].get("is_heading") and block.numbering_prefix:
        return False, 0.0, None, None

    score = 0.72
    if parent_block.numbering_prefix:
        score += 0.12
    if parent_row.get("source") == "matched":
        score += 0.08
    if next_is_body:
        score += 0.08
    if next_is_list:
        score += 0.1
    if block.prev_blank or parent_block.next_blank:
        score += 0.04
    if parent_idx == idx - 1:
        score += 0.06

    return True, round(min(1.0, score), 3), parent_level, parent_idx


def _detect_unnumbered_subheadings(
    blocks: List[AnalysisBlock],
    results: List[Dict[str, Any]],
    heading_indices: List[int],
    skip_indices: Optional[set] = None,
) -> None:
    """PASS B — promote structurally obvious unnumbered sub-headings."""
    skip_indices = skip_indices or set()
    for idx, block in enumerate(blocks):
        if idx in skip_indices:
            continue
        is_sub, confidence, parent_level, parent_idx = detect_unnumbered_subheading(
            block, blocks, idx, results,
        )
        if not is_sub or parent_level is None or parent_idx is None:
            continue

        parent_block = blocks[parent_idx]
        child_level = min(4, parent_level + 1)

        # Sibling case: numbered heading → unnumbered label → list
        next_text = (blocks[idx + 1].text or "").strip() if idx + 1 < len(blocks) else ""
        if (
            parent_idx == idx - 1
            and parent_block.numbering_prefix
            and next_text
            and _is_bullet_or_list(next_text)
        ):
            child_level = parent_level

        already_heading = bool(results[idx].get("is_heading"))
        already_matched = results[idx].get("source") == "matched"
        if already_matched:
            continue

        results[idx].update({
            "is_heading": True,
            "detection_confidence": max(
                float(results[idx].get("detection_confidence") or 0),
                confidence,
            ),
            "level": _level_label(child_level),
            "heading_kind": "unnumbered_subheading",
            "parent_level": max(1, child_level - 1) if child_level == parent_level else parent_level,
            "source": "inferred",
            "matched_template_heading": results[idx].get("matched_template_heading"),
            "match_confidence": results[idx].get("match_confidence"),
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
    *,
    min_score: float = 0.65,
) -> Tuple[Optional[str], Optional[float]]:
    """
    PASS A — match heading text to a template entry (soft/synonym/alias aware).

    Every template entry is claimed by at most one paragraph, so the second
    "Introduction" resolves to the second Introduction entry (H2), and the
    parts of a compound entry ("Assumptions" of "Assumptions & Constraints")
    cannot each claim it again.
    """
    best_name: Optional[str] = None
    best_entry: Optional[TemplateEntry] = None
    best_score = 0.0

    for entry in template:
        if entry.order in context.claimed_orders:
            continue
        base = max(
            _text_match_score(text, candidate)
            for candidate in [entry.name, *entry.aliases]
        )
        if base < min_score:
            continue
        # Only a PART of a compound title matched: prefer a full-title match elsewhere
        if base < 0.9 and _compound_parts(entry.name):
            base -= 0.05
        if not _parent_matches(context, entry):
            base *= 0.35
        if entry.level == 1:
            base = min(1.0, base + 0.05)
        if base > best_score:
            best_score = base
            best_name = entry.name
            best_entry = entry

    if best_entry is None or best_score < min_score:
        return None, None

    context.claimed_orders.add(best_entry.order)
    context.last_entry = best_entry
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
        if _synonym_match(entry.name, name) or _normalize(entry.name) == _normalize(name):
            return entry.level
    return 1


def _infer_levels_from_sequence(
    heading_indices: List[int],
    blocks: List[AnalysisBlock],
    results: List[Dict[str, Any]],
) -> None:
    """Infer levels for remaining unmatched/inferred headings using document sequence."""
    current = 1

    for idx in heading_indices:
        row = results[idx]
        if row.get("level"):
            current = _level_to_int(row["level"]) or current
            continue

        if row.get("matched_template_heading") is not None:
            current = int(str(row["level"])[1]) if row.get("level") else current
            continue

        block = blocks[idx]
        depth = _reliable_numbering_depth(block.numbering_prefix)
        if depth is not None:
            row["level"] = _level_label(depth)
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
        if not row.get("source"):
            row["source"] = "inferred"
        current = level


def _demote_compound_parts(
    blocks: List[AnalysisBlock],
    results: List[Dict[str, Any]],
    outline: List[TemplateEntry],
) -> None:
    """
    Template entry "Assumptions & Constraints" (H2):
      - document line "Assumptions & Constraints"  -> matched H2 (unchanged)
      - lines "Assumptions" / "Constraints" below it -> H3 children (not H2 siblings)
    If the document only has the parts (no combined line), the first part is the
    matched entry and its sibling parts keep the same level.
    """
    compounds = {e.name: e for e in outline if _compound_parts(e.name)}
    if not compounds:
        return

    current: Optional[Tuple[TemplateEntry, int, bool]] = None  # (entry, level, matched_is_part)
    for idx, row in enumerate(results):
        if not row.get("is_heading"):
            continue
        lvl = _level_to_int(row.get("level")) or 1

        if row.get("source") == "matched":
            entry = compounds.get(row.get("matched_template_heading"))
            if entry:
                is_part = _normalize(blocks[idx].text) != _normalize(entry.name)
                current = (entry, lvl, is_part)
            else:
                current = None
            continue

        if not current:
            continue

        entry, parent_lvl, is_part = current
        body = _normalize(blocks[idx].text)
        if any(_normalize(p) == body for p in _compound_parts(entry.name)):
            child_lvl = parent_lvl if is_part else min(4, parent_lvl + 1)
            row.update({
                "level": _level_label(child_lvl),
                "source": "inferred",
                "heading_kind": "compound_part",
                "user_decision": "keep",
            })
        elif lvl <= parent_lvl:
            current = None


def find_missing_template_headings(
    results: List[Dict[str, Any]],
    outline: List[TemplateEntry],
) -> List[Dict[str, Any]]:
    """
    Admin template headings with no matching content in the uploaded document.
    Returned as synthetic classification rows with source="missing".

    Entries are compared by their unique ``order`` (so two entries named
    "Introduction" are tracked separately). Rows without that key fall back to
    name/synonym comparison.
    """
    has_orders = any("matched_template_order" in r for r in results)
    matched_orders = {
        r.get("matched_template_order")
        for r in results
        if r.get("source") == "matched" and r.get("matched_template_order") is not None
    }
    matched_names = {
        (r.get("matched_template_heading") or "").strip().lower()
        for r in results
        if r.get("matched_template_heading") and r.get("source") == "matched"
    }

    missing: List[Dict[str, Any]] = []
    for entry in outline:
        found = False
        if has_orders:
            found = entry.order in matched_orders
        else:
            for name in matched_names:
                if not name:
                    continue
                if _normalize(name) == _normalize(entry.name) or _synonym_match(name, entry.name):
                    found = True
                    break
                if _text_match_score(name, entry.name) >= 0.65:
                    found = True
                    break
        if found:
            continue
        missing.append({
            "block_id": None,
            "paragraph_id": None,
            "text": entry.name,
            "is_heading": False,
            "matched_template_heading": entry.name,
            "level": _level_label(entry.level),
            "detection_confidence": None,
            "match_confidence": None,
            "heading_kind": None,
            "source": "missing",
            "expected_level": entry.level,
            "fix_needed": False,
            "fix_status": "missing_in_document",
            "fix_description": (
                f'Template heading "{entry.name}" (H{entry.level}) was not found '
                f"in the uploaded document."
            ),
        })
    return missing


def _is_hard_negative_heading(text: str) -> bool:
    """Return True for text that must never be treated as a heading."""
    text = (text or "").strip()
    if not text:
        return True
    if _CAPTION_RE.match(text) or _LIST_ITEM_RE.match(text):
        return True
    if _looks_like_typed_list_item(text):
        return True
    if re.match(r"^To\s+[a-z]+\b", text, re.IGNORECASE) and _word_count(text) >= 6:
        return True
    if _word_count(text) > 14 and text.rstrip().endswith((".", "?", "!")):
        return True
    return False


def _index_claude_candidates(
    blocks: List[AnalysisBlock],
    claude_candidates: Optional[List[Dict[str, Any]]],
) -> Dict[int, Dict[str, Any]]:
    """Map block index → Claude candidate using paragraph_id or block_id."""
    if not claude_candidates:
        return {}

    by_pid: Dict[str, int] = {}
    by_bid: Dict[int, int] = {}
    for idx, block in enumerate(blocks):
        if block.paragraph_id:
            by_pid[str(block.paragraph_id)] = idx
        by_bid[int(block.block_id)] = idx

    indexed: Dict[int, Dict[str, Any]] = {}
    for cand in claude_candidates:
        if not isinstance(cand, dict):
            continue
        idx: Optional[int] = None
        pid = str(cand.get("paragraph_id") or "").strip()
        if pid and pid in by_pid:
            idx = by_pid[pid]
        elif cand.get("block_id") is not None:
            try:
                idx = by_bid.get(int(cand["block_id"]))
            except (TypeError, ValueError):
                idx = None
        if idx is None:
            continue
        indexed[idx] = cand
    return indexed


def analyze_headings(
    blocks: List[AnalysisBlock],
    template: Optional[Dict[str, Any]] = None,
    *,
    include_missing: bool = False,
    claude_candidates: Optional[List[Dict[str, Any]]] = None,
    user_decisions: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Detect headings, cross-check against the template, assign levels.

    When ``claude_candidates`` is provided, Claude detections are seeded first,
    then Pass A (template) + rule negatives cross-check. Extra Claude headings
    that are not in the template become source="claude_only".

    Without Claude candidates, uses the deterministic Pass A/B pipeline.
    """
    outline = build_template_outline((template or {}).get("required_sections", []))
    decisions = {str(k): str(v).lower() for k, v in (user_decisions or {}).items()}
    claude_by_idx = _index_claude_candidates(blocks, claude_candidates)
    use_claude = bool(claude_by_idx)

    # Runs of "1. 2. 3." / "1) 2) 3)" lines are lists (or a typed TOC), not headings
    list_idx = find_numbered_list_runs(blocks)

    def _neg(i: int, t: str) -> bool:
        return (
            i in list_idx
            or _is_toc_style(blocks[i])
            or _is_hard_negative_heading(t)
        )

    results: List[Dict[str, Any]] = []
    heading_indices: List[int] = []
    context = MatchContext()

    # ── Seed rows ────────────────────────────────────────────────────────────
    for idx, block in enumerate(blocks):
        text = (block.text or "").strip()
        claude = claude_by_idx.get(idx)
        negative = _neg(idx, text)
        is_heading = False
        det_conf = 0.0
        source: Optional[str] = None
        level_label: Optional[str] = None
        heading_kind: Optional[str] = None

        if use_claude:
            if claude and not negative:
                is_heading = True
                det_conf = float(claude.get("confidence") or 0.85)
                try:
                    claude_level = max(1, min(4, int(claude.get("level") or 1)))
                except (TypeError, ValueError):
                    claude_level = 1
                # Typed numbers can be stale (old exports, "0.1", "2)"), so the
                # structural level from Claude always wins over numbering depth.
                level_label = _level_label(claude_level)
                source = "inferred" if not outline else "claude_only"
                heading_kind = "standard"
            else:
                rule_hit, rule_conf = detect_heading(block)
                if rule_hit and rule_conf >= 0.55 and not negative:
                    is_heading = True
                    det_conf = rule_conf
                    source = "inferred"
                    heading_kind = "standard"
                    depth = _reliable_numbering_depth(block.numbering_prefix)
                    style_level = _is_heading_style(block.style_name)
                    if depth is not None:
                        level_label = _level_label(depth)
                    elif style_level is not None:
                        level_label = _level_label(style_level)
                    elif not outline:
                        level_label = _level_label(1)
                else:
                    det_conf = round(1.0 - rule_conf, 3) if rule_hit else round(rule_conf, 3)
        else:
            if negative:
                is_heading, det_conf = False, 0.05
            else:
                is_heading, det_conf = detect_heading(block)
            if not is_heading:
                det_conf = round(1.0 - det_conf, 3)
            else:
                source = "inferred"
                heading_kind = "standard"
                depth = _reliable_numbering_depth(block.numbering_prefix)
                style_level = _is_heading_style(block.style_name)
                if depth is not None:
                    level_label = _level_label(depth)
                elif style_level is not None:
                    level_label = _level_label(style_level)
                elif not outline:
                    level_label = _level_label(1)

        row: Dict[str, Any] = {
            "block_id": block.block_id,
            "is_heading": is_heading,
            "matched_template_heading": None,
            "matched_template_order": None,
            "level": level_label,
            "detection_confidence": round(det_conf, 3) if is_heading else (
                det_conf if not use_claude else round(det_conf, 3)
            ),
            "match_confidence": None,
            "heading_kind": heading_kind,
            "source": source,
            "user_decision": None,
            "detected_by_claude": bool(claude) and not negative,
        }
        if is_heading:
            heading_indices.append(len(results))
        results.append(row)

    # ── PASS A — template soft-matching (cross-check) ────────────────────────
    for idx, block in enumerate(blocks):
        text = (block.text or "").strip()
        if not text or _neg(idx, text):
            continue

        matched, match_conf = match_template_heading(text, outline, context, min_score=0.65)
        if not matched:
            continue

        entry = context.last_entry
        level = entry.level if entry else (_template_level_for_name(matched, outline) or 1)

        results[idx].update({
            "is_heading": True,
            "matched_template_heading": matched,
            "matched_template_order": entry.order if entry else None,
            "match_confidence": match_conf,
            "level": _level_label(level),
            "source": "matched",
            "heading_kind": results[idx].get("heading_kind") or "standard",
            "detection_confidence": max(
                float(results[idx].get("detection_confidence") or 0),
                float(match_conf or 0),
            ),
            "user_decision": "keep",  # template matches are always kept
        })
        if idx not in heading_indices:
            heading_indices.append(idx)
        _update_match_context(context, matched, level)

    heading_indices.sort()

    # Fill levels for detected-but-unmatched headings that have numbering
    for idx in heading_indices:
        if results[idx].get("source") == "matched":
            continue
        if results[idx].get("level"):
            continue
        depth = _reliable_numbering_depth(blocks[idx].numbering_prefix)
        if depth is not None and outline:
            results[idx]["level"] = _level_label(depth)
            if not results[idx].get("source"):
                results[idx]["source"] = "inferred"

    # ── PASS B — structural heading inference ────────────────────────────────
    _detect_unnumbered_subheadings(blocks, results, heading_indices, skip_indices=list_idx)

    # Sequence-based level fill for anything still missing a level
    _infer_levels_from_sequence(heading_indices, blocks, results)

    # Compound template sections: "A & B" (H2) → parts "A", "B" become H3
    _demote_compound_parts(blocks, results, outline)

    # Finalize sources + apply user Keep/Discard for Claude-only extras
    outline_empty = len(outline) == 0

    for idx in heading_indices:
        row = results[idx]
        if not row.get("is_heading"):
            continue

        # Numbering only fills levels for rows that no one decided structurally.
        # Claude rows, matched rows and compound parts keep their own level.
        if (
            row.get("source") != "matched"
            and not outline_empty
            and row.get("heading_kind") != "compound_part"
            and not row.get("detected_by_claude")
        ):
            depth = _reliable_numbering_depth(blocks[idx].numbering_prefix)
            if depth is not None:
                row["level"] = _level_label(depth)

        if not row.get("source"):
            if row.get("matched_template_heading"):
                row["source"] = "matched"
            elif outline_empty:
                row["source"] = "inferred"
            elif row.get("detected_by_claude"):
                row["source"] = "claude_only"
            else:
                row["source"] = "inferred"

        pid = blocks[idx].paragraph_id or ""
        decision = decisions.get(str(pid)) or decisions.get(str(row.get("block_id")))

        if outline_empty:
            if row.get("source") in ("claude_only", "inferred", None):
                row["source"] = "inferred"
            row["user_decision"] = (
                decision if decision in ("keep", "discard") else "keep"
            )
            if decision == "discard":
                row["is_heading"] = False
                row["fix_needed"] = False
                row["fix_status"] = "discarded_by_user"
            continue

        if (
            row.get("detected_by_claude")
            and not row.get("matched_template_heading")
            and row.get("source") != "matched"
            and row.get("heading_kind") != "compound_part"
        ):
            row["source"] = "claude_only"

        if row.get("source") == "claude_only":
            if decision in ("keep", "discard"):
                row["user_decision"] = decision
            else:
                row["user_decision"] = "pending"
            if decision == "discard":
                row["is_heading"] = False
                row["fix_needed"] = False
                row["fix_status"] = "discarded_by_user"
        elif row.get("source") == "matched":
            row["user_decision"] = "keep"
        elif row.get("source") == "inferred":
            row["user_decision"] = decision if decision in ("keep", "discard") else "keep"
            if decision == "discard":
                row["is_heading"] = False
                row["fix_needed"] = False
                row["fix_status"] = "discarded_by_user"

    if include_missing:
        results.extend(find_missing_template_headings(results, outline))

    return results


def analyze_document_headings(
    doc: DocumentModel,
    template: Optional[Dict[str, Any]] = None,
    *,
    include_missing: bool = True,
    claude_candidates: Optional[List[Dict[str, Any]]] = None,
    user_decisions: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Analyze all paragraphs in a DocumentModel and enrich results for the API."""
    blocks = blocks_from_document(doc)
    raw = analyze_headings(
        blocks,
        template,
        include_missing=False,
        claude_candidates=claude_candidates,
        user_decisions=user_decisions,
    )

    enriched: List[Dict[str, Any]] = []
    for block, row in zip(blocks, raw):
        item = dict(row)
        item["paragraph_id"] = block.paragraph_id
        item["text"] = block.text
        enriched.append(item)

    if include_missing:
        outline = build_template_outline((template or {}).get("required_sections", []))
        enriched.extend(find_missing_template_headings(enriched, outline))

    return enriched


async def analyze_document_headings_with_claude(
    doc: DocumentModel,
    template: Optional[Dict[str, Any]] = None,
    client: Any = None,
    *,
    include_missing: bool = True,
    user_decisions: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Claude-first heading analysis for the document analyze API.

    Falls back to deterministic Pass A/B when the client is unavailable or
    Claude returns no usable candidates.
    """
    blocks = blocks_from_document(doc)
    candidates: List[Dict[str, Any]] = []
    if client is not None:
        try:
            from functions.heading_detect import detect_headings_with_claude
            candidates = await detect_headings_with_claude(client, blocks, template)
        except Exception as exc:
            print(f"[heading_analysis] Claude detection failed (fallback): {exc}")
            candidates = []

    return analyze_document_headings(
        doc,
        template,
        include_missing=include_missing,
        claude_candidates=candidates or None,
        user_decisions=user_decisions,
    )


def classify_paragraphs_for_reformat(
    paragraphs: List[Any],
    required_sections: Optional[List[Any]] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Build a paragraph-index → heading classification map for the reformatter.

    `paragraphs` may be python-docx Paragraph objects or objects with `.text`
    and optional `.style`.
    """
    blocks: List[AnalysisBlock] = []
    index_map: List[int] = []

    for idx, para in enumerate(paragraphs):
        text = (para.text or "").strip() if hasattr(para, "text") else str(para).strip()
        if not text:
            continue
        style_name = None
        try:
            style_name = para.style.name if para.style is not None else None
        except Exception:
            style_name = None
        prefix, _ = _extract_numbering_prefix(text)
        blocks.append(
            AnalysisBlock(
                block_id=len(blocks),
                text=text,
                style_name=style_name,
                numbering_prefix=prefix,
                paragraph_id=f"p{idx}",
            )
        )
        index_map.append(idx)

    template = {"required_sections": required_sections or []}
    results = analyze_headings(blocks, template, include_missing=False)

    mapping: Dict[int, Dict[str, Any]] = {}
    for block_pos, row in enumerate(results):
        if not row.get("is_heading"):
            continue
        # Never auto-apply Claude-only extras until the user keeps them
        if row.get("source") == "claude_only" and row.get("user_decision") != "keep":
            continue
        doc_idx = index_map[block_pos]
        level = _level_to_int(row.get("level")) or 1
        mapping[doc_idx] = {
            "level": level,
            "source": row.get("source") or "inferred",
            "matched_template_heading": row.get("matched_template_heading"),
            "heading_kind": row.get("heading_kind"),
            "text": blocks[block_pos].text,
        }
    return mapping


def heading_plan_from_matches(matches: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    Final analysis decisions → {paragraph index: {level, ...}} for the exporter.

    This is the ONE source of truth for export: the reformatter must apply
    exactly these headings (and demote any other Heading-styled paragraph)
    instead of re-detecting headings with its own matcher.
    """
    plan: Dict[int, Dict[str, Any]] = {}
    for m in matches or []:
        pid = str(m.get("paragraph_id") or "")
        if not (m.get("is_heading") and re.fullmatch(r"p\d+", pid)):
            continue
        if m.get("source") == "claude_only" and m.get("user_decision") != "keep":
            continue
        if m.get("fix_status") == "discarded_by_user":
            continue
        plan[int(pid[1:])] = {
            "level": _level_to_int(m.get("level")) or 1,
            "source": m.get("source"),
            "matched_template_heading": m.get("matched_template_heading"),
            "heading_kind": m.get("heading_kind"),
            "text": m.get("text"),
        }
    return plan


def _level_to_int(level: Optional[str]) -> Optional[int]:
    if not level or not str(level).lower().startswith("h"):
        return None
    try:
        return max(1, min(4, int(str(level)[1:])))
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
        source = row.get("source")

        if source == "missing":
            row.setdefault("fix_status", "missing_in_document")
            row.setdefault("fix_needed", False)
            enriched.append(row)
            continue

        if row.get("fix_status") == "discarded_by_user" or (
            source == "claude_only" and row.get("user_decision") == "discard"
        ):
            row["is_heading"] = False
            row["fix_status"] = "discarded_by_user"
            row["fix_needed"] = False
            row["fix_description"] = (
                f'Extra heading "{row.get("text", "")}" was discarded — treated as body text.'
            )
            enriched.append(row)
            continue

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
        user_decision = (row.get("user_decision") or "").lower()

        # Claude-only extras wait for Keep/Discard before style apply
        if source == "claude_only" and user_decision in ("", "pending"):
            row.update({
                "fix_status": "awaiting_confirmation",
                "fix_needed": False,
                "fix_description": (
                    f'Claude detected "{row.get("text", "")}" as a heading, but it is not '
                    f"in the template outline. Keep it as a heading or discard it."
                ),
                "expected_level": expected_level,
                "current_type": current_type,
                "current_level": current_level,
                "current_style": current_style,
                "status": "awaiting_confirmation",
                "user_decision": "pending",
                "source": "claude_only",
            })
            enriched.append(row)
            continue

        fix_needed = False
        fix_status = "ok"
        fix_description = ""

        if expected_level is None:
            fix_status = "unknown_level"
            fix_description = "Heading level could not be determined."
        elif current_type != "heading":
            fix_status = "needs_style"
            fix_needed = True
            if source == "claude_only":
                suffix = " (kept — not in template)"
            elif source == "inferred":
                suffix = " (structurally inferred — review recommended)"
            elif matched_name:
                suffix = f' for "{matched_name}"'
            else:
                suffix = ""
            fix_description = f"Apply Heading {expected_level} style{suffix}."
        elif current_level != expected_level:
            fix_status = "wrong_level"
            fix_needed = True
            suffix = f' (template: "{matched_name}")' if matched_name else ""
            fix_description = (
                f"Change from Heading {current_level} to Heading {expected_level}{suffix}."
            )
        elif source == "claude_only":
            fix_status = "claude_extra_ok"
            fix_description = (
                f'Kept as Heading {expected_level} (detected by Claude; not in template).'
            )
        elif matched_name is None or source == "inferred":
            fix_status = "unmatched" if source != "inferred" else "inferred_ok"
            if row.get("heading_kind") == "unnumbered_subheading" or source == "inferred":
                fix_description = (
                    f"Inferred sub-heading \"{row.get('text', '')}\" "
                    f"should use Heading {expected_level} style."
                )
                if current_type != "heading":
                    fix_needed = True
                    fix_status = "needs_style"
            else:
                fix_description = (
                    f"Heading \"{row.get('text', '')}\" is not in the template outline."
                )
        else:
            fix_description = (
                f"Matches template section \"{matched_name}\" at H{expected_level} "
                f"(source={source})."
            )

        row.update({
            "fix_status": fix_status,
            "fix_needed": fix_needed,
            "fix_description": fix_description,
            "expected_level": expected_level,
            "current_type": current_type,
            "current_level": current_level,
            "current_style": current_style,
            "status": "ok" if not fix_needed else fix_status,
            "source": source or ("matched" if matched_name else "inferred"),
        })
        enriched.append(row)

    return enriched


def heading_matches_to_issues(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert fixable heading matches into formatting issues for the issues pipeline."""
    issues: List[Dict[str, Any]] = []
    for match in matches:
        source = match.get("source") or (
            "matched" if match.get("matched_template_heading") else "inferred"
        )

        if source == "missing":
            issues.append({
                "function": "formatting",
                "category": "Formatting",
                "type": "missing_section",
                "severity": "major",
                "paragraph_id": "",
                "page": 0,
                "reason": match.get("fix_description") or (
                    f'Template heading "{match.get("text")}" not found in document.'
                ),
                "description": match.get("fix_description") or "",
                "suggestion": f'Add a heading for "{match.get("text")}"',
                "original": "",
                "current": "",
                "heading_level": match.get("expected_level") or _level_to_int(match.get("level")) or 1,
                "matched_template_heading": match.get("matched_template_heading") or match.get("text"),
                "issue_id": missing_heading_issue_id(str(match.get("text") or "section")),
                "source": "missing",
            })
            continue

        # Pending Claude-only extras are confirmed in the UI, not as issues yet
        if source == "claude_only" and (match.get("user_decision") or "pending") == "pending":
            continue
        if match.get("fix_status") in ("awaiting_confirmation", "discarded_by_user"):
            continue

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
            if source == "claude_only":
                extra_note = " (Claude-detected, kept by user)"
            elif source == "inferred":
                extra_note = " (structurally inferred)"
            else:
                extra_note = ""
            reason = (
                f"\"{text}\" is detected as a section heading{match_suffix}"
                f"{extra_note} but does not use Word Heading {level} style."
            )
            suggestion = f"Apply Heading {level} style"

        issues.append({
            "function": "formatting",
            "category": "Formatting",
            "type": "heading_style",
            "severity": "major" if source == "matched" else "minor",
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
            "source": source,
        })

    return issues