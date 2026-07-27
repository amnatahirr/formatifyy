"""
image_formatting_service.py — Phase 1 orchestrator for image caption/numbering/refs/LOF.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

from services.image_caption_service import detect_captions_for_document
from services.image_config import get_image_format_config
from services.image_numbering_service import (
    apply_numbering_to_captions,
    assign_figure_numbers,
)
from services.image_reference_validator import validate_figure_references
from services.list_of_figures_service import regenerate_list_of_figures


def run_image_formatting_pipeline(
    file_path: str,
    output_path: str,
    formatting_rules: Dict[str, Any] | None = None,
    *,
    removed_image_ids: Optional[List[str]] = None,
    previous_labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Caption detect → number → validate refs → regenerate LOF.
    Mutates a copy at output_path. Does not invent missing caption text.
    """
    from docx import Document

    if not file_path.endswith(".docx"):
        return {
            "status": "error",
            "message": "Only DOCX supported",
            "total_images": 0,
        }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    shutil.copy2(file_path, output_path)
    doc = Document(output_path)
    cfg = get_image_format_config(formatting_rules)

    # Task 1 — detect
    caption_report = detect_captions_for_document(doc, formatting_rules)
    # Strip private refs for JSON-safe copy
    captions_public = [
        {k: v for k, v in row.items() if not k.startswith("_")}
        for row in caption_report
    ]

    # Task 2 — assign + apply numbers (idempotent)
    assignments_raw = assign_figure_numbers(doc, formatting_rules)
    applied = apply_numbering_to_captions(doc, assignments_raw, formatting_rules)

    # Re-detect after numbering for updated caption texts
    caption_after = detect_captions_for_document(doc, formatting_rules)
    captions_after_public = [
        {k: v for k, v in row.items() if not k.startswith("_")}
        for row in caption_after
    ]

    # Task 3 — references
    ref_report = validate_figure_references(
        doc,
        applied,
        removed_image_ids=removed_image_ids,
        previous_labels=previous_labels,
    )

    # Task 5 — LOF
    lof_report = regenerate_list_of_figures(doc, applied, formatting_rules)

    doc.save(output_path)

    missing = sum(1 for c in captions_after_public if c.get("caption_missing"))
    return {
        "status": "success" if applied else "no_images",
        "message": (
            f"Processed {len(applied)} image(s)"
            if applied
            else "No images found"
        ),
        "total_images": len(applied),
        "config": cfg,
        "captions": captions_after_public,
        "captions_before": captions_public,
        "numbering": applied,
        "references": ref_report,
        "list_of_figures": lof_report,
        "caption_missing_count": missing,
        "output_filename": os.path.basename(output_path),
    }
