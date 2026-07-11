"""Parse uploaded DOCX files into template section content."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from heading_analysis import (
    MatchContext,
    _extract_numbering_prefix,
    _normalize,
    _synonym_match,
    _update_match_context,
    _word_count,
    analyze_document_headings,
    blocks_from_document,
    build_template_outline,
    detect_heading,
)
from parser import parse_file
from vc.utils import section_slug


_LIST_ITEM_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219•\-*–·]\s+")
_CAPTION_RE = re.compile(
    r"^(figure|fig\.?|table|tab\.?|image|chart|diagram|equation|eq\.?)\s*[\d.:]+",
    re.IGNORECASE,
)


def _resolve_section_id(
    matched_name: str,
    template_sections: List[Dict[str, Any]],
) -> Optional[str]:
    for sec in template_sections:
        if _synonym_match(sec["section_name"], matched_name):
            return sec["section_id"]
    return None


def _strict_section_boundary_match(
    text: str,
    template_sections: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Match only clear section titles — exact name, synonym, or short numbered heading.
    Avoids false positives like 'Introduction paragraph one...' matching Introduction.
    """
    stripped = (text or "").strip()
    if not stripped or _LIST_ITEM_RE.match(stripped) or _CAPTION_RE.match(stripped):
        return None

    prefix, body = _extract_numbering_prefix(stripped)
    candidate = (body or stripped).strip()
    norm = _normalize(candidate)

    if not norm:
        return None

    # Numbered headings ("1. Introduction") — allow slightly longer titles
    max_words = 10 if prefix else 6
    if _word_count(candidate) > max_words:
        return None

    # Body sentences ending with punctuation are not section titles
    if candidate.rstrip().endswith((".", "?", "!")) and _word_count(candidate) > 4:
        return None

    for sec in template_sections:
        name = sec["section_name"]
        norm_name = _normalize(name)
        if norm == norm_name or _synonym_match(candidate, name):
            return sec["section_id"]

    return None


def _append_content(result: Dict[str, str], section_id: str, text: str) -> None:
    if result[section_id]:
        result[section_id] += "\n\n" + text
    else:
        result[section_id] = text


def extract_sections_from_docx(
    file_path: str,
    template_sections: List[Dict[str, Any]],
) -> Dict[str, str]:
    """
    Parse a DOCX and map paragraph content to template sections.

    Uses the same heading detection + template matching pipeline as the main
    analysis engine, so sections are found even when authors use bold/normal
    paragraphs instead of Word Heading styles.
    """
    filename = os.path.basename(file_path)
    doc_model = parse_file(file_path, filename)

    template_payload = {
        "required_sections": [
            {
                "name": sec["section_name"],
                "heading_level": int(sec.get("heading_level") or 1),
            }
            for sec in template_sections
        ]
    }

    analysis = analyze_document_headings(doc_model, template_payload)
    outline = build_template_outline(template_payload["required_sections"])

    result: Dict[str, str] = {sec["section_id"]: "" for sec in template_sections}
    current_section: Optional[str] = None
    match_context = MatchContext()

    for item in analysis:
        text = (item.get("text") or "").strip()
        if not text:
            continue

        is_heading = bool(item.get("is_heading"))
        matched_name = item.get("matched_template_heading")
        heading_kind = item.get("heading_kind")

        # Sub-headings within a section are kept as content.
        if heading_kind == "unnumbered_subheading":
            if current_section:
                _append_content(result, current_section, text)
            continue

        section_boundary: Optional[str] = None

        if matched_name:
            section_boundary = _resolve_section_id(matched_name, template_sections)

        if not section_boundary and is_heading:
            section_boundary = _strict_section_boundary_match(text, template_sections)

        if section_boundary:
            current_section = section_boundary
            if matched_name:
                level = 1
                for entry in outline:
                    if _synonym_match(entry.name, matched_name):
                        level = entry.level
                        break
                _update_match_context(match_context, matched_name, level)
            continue

        if is_heading and current_section:
            _append_content(result, current_section, text)
            continue

        if current_section:
            _append_content(result, current_section, text)
        elif _strict_section_boundary_match(text, template_sections) is None:
            # Preamble before first section (title page, author lines, etc.)
            title_page = next(
                (s["section_id"] for s in template_sections if s["section_id"] == "title_page"),
                template_sections[0]["section_id"] if template_sections else None,
            )
            if title_page:
                _append_content(result, title_page, text)

    # Fallback if heading pipeline found almost nothing
    filled = sum(1 for v in result.values() if v.strip())
    if filled <= 1:
        result = _fallback_extract_by_titles(doc_model, template_sections)

    return result


def _fallback_extract_by_titles(
    doc_model,
    template_sections: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Second pass using per-block heading detection + strict title matching."""
    blocks = blocks_from_document(doc_model)
    result: Dict[str, str] = {sec["section_id"]: "" for sec in template_sections}
    current_section: Optional[str] = None

    for block in blocks:
        text = (block.text or "").strip()
        if not text:
            continue

        is_heading, _ = detect_heading(block)
        section_boundary = None

        if is_heading:
            section_boundary = _strict_section_boundary_match(text, template_sections)

        if section_boundary:
            current_section = section_boundary
            continue

        if current_section:
            _append_content(result, current_section, text)
        else:
            title_page = next(
                (s["section_id"] for s in template_sections if s["section_id"] == "title_page"),
                None,
            )
            if title_page:
                _append_content(result, title_page, text)

    return result
