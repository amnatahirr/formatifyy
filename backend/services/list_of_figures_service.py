"""
list_of_figures_service.py — Regenerate List of Figures after numbering.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from docx_fields import (
    _LOF_HEADING_RE,
    _find_section_heading_paragraph,
    _get_max_bookmark_id,
    _ensure_bookmark_on_paragraph,
    _remove_lof_field_block,
    ensure_update_fields_on_open,
    estimate_body_page_numbers,
    insert_lof_field,
    is_paragraph_in_cover_or_info,
    paragraph_has_image,
    paragraph_is_figure_caption,
)
from services.image_caption_service import _find_caption_near
from services.image_config import get_image_format_config


def regenerate_list_of_figures(
    doc,
    assignments: List[Dict[str, Any]],
    formatting_rules: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Rebuild LOF from current image captions / numbering assignments.
    Idempotent: removes prior LOF block then re-inserts.
    """
    cfg = get_image_format_config(formatting_rules)
    if not cfg.get("include_lof", True):
        return {"lof_added": False, "skipped": True, "reason": "include_lof=false"}

    entries = _build_lof_entries(doc, assignments)
    if not entries:
        return {
            "lof_added": False,
            "lof_entry_count": 0,
            "error": "No figure captions available for List of Figures",
        }

    _remove_lof_field_block(doc)
    ensure_update_fields_on_open(doc)
    heading = _find_section_heading_paragraph(doc, _LOF_HEADING_RE)
    insert_lof_field(doc, heading_para=heading, entries=entries)

    return {
        "lof_added": True,
        "lof_entry_count": len(entries),
        "entries": [
            {"text": e.get("text"), "bookmark": e.get("bookmark")} for e in entries
        ],
    }


def _build_lof_entries(
    doc, assignments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    next_bookmark_id = _get_max_bookmark_id(doc) + 1
    entries: List[Dict[str, Any]] = []
    by_id = {a["image_id"]: a for a in assignments}

    img_i = 0
    page_map = estimate_body_page_numbers(doc)
    for idx, para in enumerate(doc.paragraphs):
        if not paragraph_has_image(para):
            continue
        # Cover logo / project-info images never appear in LOF
        if is_paragraph_in_cover_or_info(doc, para):
            continue
        image_id = f"img{img_i}"
        img_i += 1
        a = by_id.get(image_id, {})

        cap_para, _pos, raw = _find_caption_near(doc, para)
        if cap_para is None:
            continue

        text = (a.get("label") or "").strip()
        if not text:
            text = (cap_para.text or "").strip() or (raw or "").strip()
        if not text and not paragraph_is_figure_caption(cap_para):
            continue

        # Prefer assigned label for LOF display (SEQ plain-text may lack numbers)
        if a.get("label"):
            text = a["label"]
        elif a.get("caption_description") is not None and a.get("n") is not None:
            ch = a.get("chapter")
            if ch is not None:
                text = f"Figure {ch}.{a['n']}: {a.get('caption_description') or ''}".strip()
            else:
                text = f"Figure {a['n']}: {a.get('caption_description') or ''}".strip()

        bookmark_name = f"_Toc{next_bookmark_id:09d}"
        _ensure_bookmark_on_paragraph(cap_para, bookmark_name, next_bookmark_id)
        entries.append(
            {
                "paragraph_index": idx,
                "level": 1,
                "text": text or a.get("label") or f"Figure {a.get('n', '?')}",
                "bookmark": bookmark_name,
                "page": page_map.get(
                    cap_para._element, page_map.get(para._element, 1)
                ),
            }
        )
        next_bookmark_id += 1

    return entries
