"""
table_formatting_service.py — Orchestrator for template-driven table formatting.

Pipeline: detect captions → number → validate refs → apply visual styles → LOT.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional, Set

from services.list_of_tables_service import regenerate_list_of_tables
from services.table_caption_service import detect_captions_for_tables
from services.table_config import get_table_format_config
from services.table_numbering_service import (
    apply_numbering_to_table_captions,
    assign_table_numbers,
)
from services.table_reference_validator import validate_table_references
from table_processor import format_table


def run_table_formatting_pipeline(
    file_path: str,
    output_path: str,
    formatting_rules: Dict[str, Any] | None = None,
    *,
    selected_indices: Optional[Set[int]] = None,
    removed_table_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Caption detect → number/create → validate refs → style tables → regenerate LOT.
    Mutates a copy at output_path.
    """
    from docx import Document
    from docx_fields import _element_is_before_body_start

    if not file_path.endswith(".docx"):
        return {
            "status": "error",
            "message": "Only DOCX supported",
            "total_tables": 0,
        }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    shutil.copy2(file_path, output_path)
    doc = Document(output_path)
    cfg = get_table_format_config(formatting_rules)
    captioned = cfg["captioned"]
    style = cfg["table_style"]

    # 1 — detect
    caption_report = detect_captions_for_tables(doc, formatting_rules)
    captions_public = [
        {k: v for k, v in row.items() if not k.startswith("_")}
        for row in caption_report
    ]

    # 2 — assign + apply numbers / create missing captions
    assignments_raw = assign_table_numbers(doc, formatting_rules)
    applied = apply_numbering_to_table_captions(
        doc, assignments_raw, formatting_rules
    )

    caption_after = detect_captions_for_tables(doc, formatting_rules)
    captions_after_public = [
        {k: v for k, v in row.items() if not k.startswith("_")}
        for row in caption_after
    ]

    # 3 — references
    ref_report = validate_table_references(
        doc,
        applied,
        require_intext_reference=bool(captioned.get("require_intext_reference")),
        removed_table_ids=removed_table_ids,
    )

    # 4 — visual styles
    formatted_indices: List[int] = []
    style_notes: List[Dict[str, Any]] = []
    body_i = -1
    for index, table in enumerate(doc.tables):
        if _element_is_before_body_start(doc, table._tbl):
            continue
        body_i += 1
        if selected_indices is not None and index not in selected_indices:
            continue
        info = format_table(table, style) or {}
        formatted_indices.append(index)
        if info.get("notes"):
            style_notes.append({"index": index, "notes": info["notes"]})

    # 5 — LOT
    lot_report = regenerate_list_of_tables(doc, applied, formatting_rules)

    doc.save(output_path)

    missing = sum(1 for c in captions_after_public if c.get("caption_missing"))
    require_caption = bool(captioned.get("require_caption", True))
    status = "success" if applied else "no_tables"
    if require_caption and missing > 0:
        # Still success if we attempted creation; residual missing is reported
        pass

    return {
        "status": status,
        "message": (
            f"Processed {len(applied)} table(s)"
            if applied
            else "No body tables found"
        ),
        "total_tables": len(applied),
        "config": {
            k: cfg[k]
            for k in (
                "table_caption_position",
                "table_caption_format_pattern",
                "table_numbering_scheme",
                "include_lot",
                "table_require_caption",
                "table_require_intext_reference",
                "list_of_tables_format",
            )
        },
        "table_style": style,
        "captions": captions_after_public,
        "captions_before": captions_public,
        "numbering": applied,
        "references": ref_report,
        "list_of_tables": lot_report,
        "formatted_tables": formatted_indices,
        "style_notes": style_notes,
        "caption_missing_count": missing,
        "output_filename": os.path.basename(output_path),
    }
