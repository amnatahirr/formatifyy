"""
list_of_tables_service.py — Regenerate List of Tables after numbering.
"""

from __future__ import annotations

from typing import Any, Dict, List

from docx_fields import (
    _LOT_HEADING_RE,
    _element_is_before_body_start,
    _ensure_bookmark_on_paragraph,
    _find_section_heading_paragraph,
    _get_max_bookmark_id,
    _remove_lot_field_block,
    analyze_document_lists,
    arrange_front_matter_lists,
    ensure_update_fields_on_open,
    estimate_body_page_numbers,
    insert_lot_field,
)
from services.table_caption_service import find_caption_near_table
from services.table_config import format_table_caption_label, get_table_format_config


def regenerate_list_of_tables(
    doc,
    assignments: List[Dict[str, Any]],
    formatting_rules: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Rebuild LOT from current table captions / numbering assignments.
    Idempotent: removes prior LOT block then re-inserts.
    """
    cfg = get_table_format_config(formatting_rules)
    if not cfg.get("include_lot", True):
        return {"lot_added": False, "skipped": True, "reason": "include_lot=false"}

    entries = _build_lot_entries(doc, assignments, cfg)
    if not entries:
        return {
            "lot_added": False,
            "lot_entry_count": 0,
            "error": "No table captions available for List of Tables",
        }

    _remove_lot_field_block(doc)
    ensure_update_fields_on_open(doc)
    heading = _find_section_heading_paragraph(doc, _LOT_HEADING_RE)
    insert_lot_field(doc, heading_para=heading, entries=entries)

    # Keep Cover → Info → TOC → LOF → LOT → Body after LOT rebuild
    lists_status = analyze_document_lists(doc)
    layout = arrange_front_matter_lists(
        doc,
        include_toc=bool(lists_status.get("has_toc")),
        include_lof=bool(lists_status.get("has_lof")),
        include_lot=True,
    )

    return {
        "lot_added": True,
        "lot_entry_count": len(entries),
        "front_matter_layout": layout,
        "entries": [
            {"text": e.get("text"), "bookmark": e.get("bookmark")} for e in entries
        ],
    }


def _build_lot_entries(
    doc, assignments: List[Dict[str, Any]], cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    next_bookmark_id = _get_max_bookmark_id(doc) + 1
    entries: List[Dict[str, Any]] = []
    by_id = {a["table_id"]: a for a in assignments}
    list_pattern = cfg.get("list_of_tables_format") or cfg.get(
        "table_caption_format_pattern"
    )
    page_map = estimate_body_page_numbers(doc)

    tbl_i = 0
    for table in doc.tables:
        if _element_is_before_body_start(doc, table._tbl):
            continue
        table_id = f"tbl{tbl_i}"
        tbl_i += 1
        a = by_id.get(table_id, {})

        cap_para, _pos, raw = find_caption_near_table(doc, table)
        if cap_para is None:
            continue

        desc = a.get("caption_description") or ""
        if a.get("n") is not None:
            text = format_table_caption_label(
                pattern=list_pattern,
                n=int(a["n"]),
                chapter=a.get("chapter"),
                description=desc,
            )
        else:
            text = (a.get("label") or "").strip() or (cap_para.text or "").strip() or (
                raw or ""
            ).strip()

        if not text:
            continue

        bookmark_name = f"_Toc{next_bookmark_id:09d}"
        _ensure_bookmark_on_paragraph(cap_para, bookmark_name, next_bookmark_id)
        entries.append(
            {
                "level": 1,
                "text": text,
                "bookmark": bookmark_name,
                "page": page_map.get(cap_para._element, 1),
            }
        )
        next_bookmark_id += 1

    return entries
