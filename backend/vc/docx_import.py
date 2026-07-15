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


_LIST_ITEM_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219•\-*–·]\s+")
_CAPTION_RE = re.compile(
    r"^(figure|fig\.?|table|tab\.?|image|chart|diagram|equation|eq\.?)\s*[\d.:]+",
    re.IGNORECASE,
)


def _format_heading_check_line(
    text: str,
    diag: Dict[str, Any],
    *,
    result: str,
    prefix: str = "[HEADING-CHECK]",
) -> str:
    snippet = (text or "").replace("\n", " ").strip()
    if len(snippet) > 80:
        snippet = snippet[:77] + "..."
    parts = [f"{prefix} {snippet!r} -> {result}"]
    if diag.get("score") is not None:
        parts.append(f"score={diag['score']}")
    if diag.get("layer"):
        parts.append(f"layer={diag['layer']}")
    return " | ".join(parts)


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


def _section_display_name(
    section_id: Optional[str],
    template_sections: List[Dict[str, Any]],
) -> str:
    if not section_id:
        return "(none)"
    for sec in template_sections:
        if sec["section_id"] == section_id:
            return sec["section_name"]
    return section_id


def _log_heading_check(
    text: str,
    block_index: Optional[int],
    result: str,
    *,
    prefix: str = "[HEADING-CHECK]",
    extra_diag: Optional[Dict[str, Any]] = None,
) -> None:
    del block_index  # retained for call-site compatibility
    diag = dict(extra_diag or {})
    print(_format_heading_check_line(text, diag, result=result, prefix=prefix), flush=True)


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

    print(f"[HEADING-CHECK] === section extraction: {filename} ===", flush=True)

    for item in analysis:
        text = (item.get("text") or "").strip()
        # Current pipeline exposes block_id; older logs used block_index
        block_index = item.get("block_index")
        if block_index is None:
            block_index = item.get("block_id")
        if block_index is None and item.get("source") == "missing":
            continue
        if block_index is None and not text:
            continue
        if not text:
            _log_heading_check(text, block_index, "skipped (empty)")
            continue

        is_heading = bool(item.get("is_heading"))
        matched_name = item.get("matched_template_heading")
        heading_kind = item.get("heading_kind")
        current_name = _section_display_name(current_section, template_sections)

        # Sub-headings within a section are kept as content.
        if heading_kind == "unnumbered_subheading":
            if current_section:
                _append_content(result, current_section, text)
                _log_heading_check(
                    text,
                    block_index,
                    f'absorbed as subheading into "{current_name}"',
                )
            else:
                _log_heading_check(
                    text,
                    block_index,
                    "subheading with no active section (dropped)",
                )
            continue

        section_boundary: Optional[str] = None

        if matched_name:
            section_boundary = _resolve_section_id(matched_name, template_sections)

        if not section_boundary and is_heading:
            section_boundary = _strict_section_boundary_match(text, template_sections)

        if section_boundary:
            new_name = _section_display_name(section_boundary, template_sections)
            via = f'template match "{matched_name}"' if matched_name else "strict boundary"
            _log_heading_check(
                text,
                block_index,
                f'new section started -> "{new_name}" ({via})',
            )
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
            _log_heading_check(
                text,
                block_index,
                f'absorbed into "{current_name}" (heading without section boundary)',
            )
            continue

        if current_section:
            _append_content(result, current_section, text)
            _log_heading_check(text, block_index, f'absorbed into "{current_name}"')
            continue

        if _strict_section_boundary_match(text, template_sections) is None:
            title_page = next(
                (s["section_id"] for s in template_sections if s["section_id"] == "title_page"),
                template_sections[0]["section_id"] if template_sections else None,
            )
            if title_page:
                _append_content(result, title_page, text)
                preamble_name = _section_display_name(title_page, template_sections)
                _log_heading_check(
                    text,
                    block_index,
                    f'preamble absorbed into "{preamble_name}"',
                )
            else:
                _log_heading_check(text, block_index, "preamble with no target section")
        else:
            _log_heading_check(text, block_index, "no active section (content dropped)")

    # Fallback if heading pipeline found almost nothing
    filled = sum(1 for v in result.values() if v.strip())
    if filled <= 1:
        print("[HEADING-CHECK] === fallback title-matching pass ===", flush=True)
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

    for block_idx, block in enumerate(blocks):
        text = (block.text or "").strip()
        if not text:
            continue

        is_heading, det_conf = detect_heading(block)
        section_boundary = None

        if is_heading:
            section_boundary = _strict_section_boundary_match(text, template_sections)

        current_name = _section_display_name(current_section, template_sections)
        diag = {
            "layer": "fallback_structural_scoring",
            "score": det_conf,
            "structural_pass": is_heading,
            "template_match": {
                "kind": "STRICT_BOUNDARY" if section_boundary else "NONE",
                "name": _section_display_name(section_boundary, template_sections) if section_boundary else None,
            },
        }

        if section_boundary:
            new_name = _section_display_name(section_boundary, template_sections)
            print(
                _format_heading_check_line(
                    text,
                    diag,
                    result=f'new section started -> "{new_name}" (strict boundary)',
                    prefix="[HEADING-CHECK-FALLBACK]",
                ),
                flush=True,
            )
            current_section = section_boundary
            continue

        if current_section:
            _append_content(result, current_section, text)
            print(
                _format_heading_check_line(
                    text,
                    diag,
                    result=f'absorbed into "{current_name}"',
                    prefix="[HEADING-CHECK-FALLBACK]",
                ),
                flush=True,
            )
        else:
            title_page = next(
                (s["section_id"] for s in template_sections if s["section_id"] == "title_page"),
                None,
            )
            if title_page:
                _append_content(result, title_page, text)
                preamble_name = _section_display_name(title_page, template_sections)
                print(
                    _format_heading_check_line(
                        text,
                        diag,
                        result=f'preamble absorbed into "{preamble_name}"',
                        prefix="[HEADING-CHECK-FALLBACK]",
                    ),
                    flush=True,
                )

    return result
