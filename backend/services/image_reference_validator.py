"""
image_reference_validator.py — Cross-check in-text figure references vs images.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from docx_tools.docx_fields import paragraph_has_image, paragraph_is_figure_caption

# Explicit numbered refs: Figure 3.1 / Fig. 2 / figure 12
_EXPLICIT_REF_RE = re.compile(
    r"\b(?:figures?|figs?\.?)\s*(\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)
# Soft / unnumbered pointers (warnings only)
_SOFT_REF_RE = re.compile(
    r"\b(?:as\s+)?(?:shown|illustrated|depicted|presented)\s+(?:in\s+)?(?:the\s+)?(?:figure|fig\.?|above|below)\b"
    r"|\b(?:see|refer\s+to)\s+(?:the\s+)?(?:figure|fig\.?)\b"
    r"|\b(?:figure|fig\.?)\s+(?:above|below)\b",
    re.IGNORECASE,
)


def _existing_figure_keys(assignments: List[Dict[str, Any]]) -> Set[str]:
    keys: Set[str] = set()
    for a in assignments:
        if a.get("chapter") is not None:
            keys.add(f"{a['chapter']}.{a['n']}")
            keys.add(str(a["n"]))  # also allow bare n within soft matching later
        else:
            keys.add(str(a["n"]))
    return keys


def validate_figure_references(
    doc,
    assignments: List[Dict[str, Any]],
    *,
    removed_image_ids: Optional[List[str]] = None,
    previous_labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Scan body text for figure references and cross-check against assigned numbers.

    Returns:
      {
        orphaned_images: [{image_id, label, reason}],
        broken_references: [{text, number, paragraph_index, reason}],
        soft_references: [...],
        valid: bool,
      }
    """
    removed = set(removed_image_ids or [])
    existing_keys = _existing_figure_keys(assignments)
    # Labels currently expected in text after numbering
    expected_labels = {
        (a.get("label") or "").strip().lower()
        for a in assignments
        if a.get("label")
    }

    referenced_keys: Set[str] = set()
    broken: List[Dict[str, Any]] = []
    soft: List[Dict[str, Any]] = []

    for p_idx, para in enumerate(doc.paragraphs):
        if paragraph_has_image(para) or paragraph_is_figure_caption(para):
            continue
        text = (para.text or "").strip()
        if not text:
            continue

        for m in _EXPLICIT_REF_RE.finditer(text):
            num = m.group(1)
            referenced_keys.add(num)
            snippet = text[max(0, m.start() - 20) : m.end() + 40].strip()
            if num not in existing_keys:
                broken.append(
                    {
                        "text": snippet,
                        "number": num,
                        "paragraph_index": p_idx,
                        "reason": "no_matching_figure",
                    }
                )

        if _SOFT_REF_RE.search(text):
            soft.append(
                {
                    "text": text[:160],
                    "paragraph_index": p_idx,
                    "reason": "unnumbered_or_relative_reference",
                }
            )

    # Stale previous labels (e.g. after renumber / remove)
    if previous_labels:
        for lab in previous_labels:
            lab_s = (lab or "").strip()
            if not lab_s:
                continue
            # Extract number token from old label
            m = _EXPLICIT_REF_RE.search(lab_s)
            if not m:
                continue
            old_num = m.group(1)
            if old_num in existing_keys:
                continue
            # If document still mentions old number → already in broken; else note removed
            still_mentioned = any(b["number"] == old_num for b in broken)
            if not still_mentioned:
                # Check raw doc for old number
                for p_idx, para in enumerate(doc.paragraphs):
                    if old_num in (para.text or "") and _EXPLICIT_REF_RE.search(para.text or ""):
                        broken.append(
                            {
                                "text": (para.text or "")[:160],
                                "number": old_num,
                                "paragraph_index": p_idx,
                                "reason": "stale_after_renumber_or_remove",
                            }
                        )
                        break

    orphaned: List[Dict[str, Any]] = []
    for a in assignments:
        if a["image_id"] in removed:
            continue
        keys = set()
        if a.get("chapter") is not None:
            keys.add(f"{a['chapter']}.{a['n']}")
        keys.add(str(a["n"]))
        if keys.isdisjoint(referenced_keys):
            orphaned.append(
                {
                    "image_id": a["image_id"],
                    "label": a.get("label") or f"Figure {a['n']}",
                    "reason": "no_in_text_reference",
                }
            )

    # Removed images that still have references
    for rid in removed:
        # Caller may pass labels via previous_labels; mark generic broken if any refs unmatched
        pass

    valid = len(broken) == 0
    return {
        "orphaned_images": orphaned,
        "broken_references": broken,
        "soft_references": soft,
        "valid": valid,
        "referenced_numbers": sorted(referenced_keys),
        "existing_numbers": sorted(existing_keys),
    }
