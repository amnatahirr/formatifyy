"""Utility helpers for the VC module."""

from __future__ import annotations

import re
from typing import Any, Dict, List


def section_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return slug or "section"


def parse_template_sections(required_sections: List[Any]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
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
        sections.append({
            "section_id": section_slug(name),
            "section_name": name,
            "template_order": idx + 1,
            "heading_level": max(1, min(4, level)),
        })
    return sections


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def word_overlap_ratio(text_a: str, text_b: str) -> float:
    words_a = tokenize(text_a)
    words_b = tokenize(text_b)
    if not words_a or not words_b:
        return 0.0
    overlap = words_a & words_b
    smaller = min(len(words_a), len(words_b))
    return len(overlap) / smaller if smaller else 0.0


_SECTION_TOPIC_HINTS: Dict[str, List[str]] = {
    "introduction": ["introduction", "background", "overview", "objective", "aim", "purpose", "scope"],
    "abstract": ["abstract", "summary", "overview"],
    "literature": ["literature", "review", "related", "prior", "research", "studies"],
    "methodology": ["method", "methodology", "approach", "design", "procedure", "experiment", "sample"],
    "results": ["result", "finding", "data", "analysis", "outcome"],
    "discussion": ["discussion", "interpret", "implication", "limitation"],
    "conclusion": ["conclusion", "summary", "recommendation", "future"],
    "references": ["reference", "bibliography", "citation", "source"],
    "acknowledgement": ["acknowledge", "thanks", "gratitude"],
    "appendix": ["appendix", "supplementary"],
}


def content_matches_section(section_name: str, content: str) -> tuple[bool, float, str]:
    """Heuristic: does section body plausibly belong under this section title?"""
    if not (content or "").strip():
        return True, 1.0, "Empty section"

    norm_name = section_name.lower().strip()
    name_tokens = tokenize(norm_name)
    content_tokens = tokenize(content[:2000])

    if not content_tokens:
        return True, 1.0, "No content tokens"

    direct_overlap = name_tokens & content_tokens
    if direct_overlap:
        return True, min(1.0, 0.6 + 0.1 * len(direct_overlap)), "Section title terms appear in content"

    for key, hints in _SECTION_TOPIC_HINTS.items():
        if key in norm_name or any(tok in norm_name for tok in key.split("_")):
            hint_hits = sum(1 for h in hints if h in content_tokens)
            if hint_hits >= 2:
                return True, 0.75, f"Topic keywords match ({hint_hits} hits)"
            if hint_hits == 1:
                return True, 0.55, "Weak topic keyword match"

    first_words = " ".join(list(content_tokens)[:40])
    if any(tok in first_words for tok in name_tokens if len(tok) > 3):
        return True, 0.5, "Partial title overlap"

    return False, 0.2, "Content does not appear to match section topic"
