"""
table_reference_validator.py — Cross-check in-text table references vs tables.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from services.table_caption_service import _paragraph_is_table_caption

_EXPLICIT_REF_RE = re.compile(
    r"\b(?:tables?|tbls?\.?)\s*(\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)
_SOFT_REF_RE = re.compile(
    r"\b(?:as\s+)?(?:shown|illustrated|presented|listed)\s+(?:in\s+)?(?:the\s+)?(?:table|tbl\.?|above|below)\b"
    r"|\b(?:see|refer\s+to)\s+(?:the\s+)?(?:table|tbl\.?)\b"
    r"|\b(?:table|tbl\.?)\s+(?:above|below)\b",
    re.IGNORECASE,
)


def _existing_table_keys(assignments: List[Dict[str, Any]]) -> Set[str]:
    keys: Set[str] = set()
    for a in assignments:
        if a.get("chapter") is not None:
            keys.add(f"{a['chapter']}.{a['n']}")
            keys.add(str(a["n"]))
        else:
            keys.add(str(a["n"]))
    return keys


def validate_table_references(
    doc,
    assignments: List[Dict[str, Any]],
    *,
    require_intext_reference: bool = False,
    removed_table_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Scan body text for table references and cross-check against assigned numbers.
    """
    removed = set(removed_table_ids or [])
    existing_keys = _existing_table_keys(assignments)

    referenced_keys: Set[str] = set()
    broken: List[Dict[str, Any]] = []
    soft: List[Dict[str, Any]] = []

    for p_idx, para in enumerate(doc.paragraphs):
        if _paragraph_is_table_caption(para):
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
                        "reason": "no_matching_table",
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

    orphaned: List[Dict[str, Any]] = []
    for a in assignments:
        if a["table_id"] in removed:
            continue
        keys = set()
        if a.get("chapter") is not None:
            keys.add(f"{a['chapter']}.{a['n']}")
        keys.add(str(a["n"]))
        if keys.isdisjoint(referenced_keys):
            orphaned.append(
                {
                    "table_id": a["table_id"],
                    "label": a.get("label") or f"Table {a['n']}",
                    "reason": "no_in_text_reference",
                }
            )

    missing_required = orphaned if require_intext_reference else []
    valid = len(broken) == 0 and (
        not require_intext_reference or len(orphaned) == 0
    )
    return {
        "orphaned_tables": orphaned,
        "broken_references": broken,
        "soft_references": soft,
        "missing_required_references": missing_required,
        "valid": valid,
        "referenced_numbers": sorted(referenced_keys),
        "existing_numbers": sorted(existing_keys),
        "require_intext_reference": require_intext_reference,
    }
