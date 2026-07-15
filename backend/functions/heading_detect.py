"""
functions/heading_detect.py — Claude-first structural heading detection.

Returns candidate headings for every paragraph that functions as a section
or subsection title. Downstream code cross-checks these against the template
outline and deterministic rules.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from config import ANALYSIS_MODEL

_BATCH_SIZE = 80


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text or "").strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract the largest {...} object
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"headings": [], "error": True}


def _block_payload(blocks: Sequence[Any]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for b in blocks:
        text = (getattr(b, "text", None) or "").strip()
        if not text:
            continue
        payload.append({
            "paragraph_id": getattr(b, "paragraph_id", "") or "",
            "block_id": getattr(b, "block_id", None),
            "text": text[:500],
            "style": getattr(b, "style_name", None) or "",
            "numbering_prefix": getattr(b, "numbering_prefix", None) or "",
        })
    return payload


def _template_section_names(template: Optional[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for sec in (template or {}).get("required_sections", []) or []:
        if isinstance(sec, dict):
            name = str(sec.get("name") or "").strip()
        else:
            name = str(sec).strip()
        if name:
            names.append(name)
    return names


async def detect_headings_with_claude(
    client: Any,
    blocks: Sequence[Any],
    template: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Ask Claude to identify every section / subsection heading in the document.

    Returns a list of:
      { paragraph_id, block_id?, text?, level (1-4), confidence (0-1) }
    """
    payload = _block_payload(blocks)
    if not payload or client is None:
        return []

    section_names = _template_section_names(template)
    outline_hint = (
        json.dumps(section_names, indent=2)
        if section_names
        else "[]  (no required_sections provided — detect headings structurally)"
    )

    all_candidates: List[Dict[str, Any]] = []
    seen_pids: set[str] = set()

    for start in range(0, len(payload), _BATCH_SIZE):
        chunk = payload[start : start + _BATCH_SIZE]
        prompt = f"""You are an expert academic document structure analyzer.
Identify EVERY paragraph that is a section or subsection HEADING (title), not body text.

TEMPLATE SECTION NAMES (hints only — also detect real headings not on this list):
{outline_hint}

PARAGRAPHS:
{json.dumps(chunk, indent=2)}

RULES:
1. A heading is a short standalone title that introduces a section or subsection.
2. Include numbered headings (e.g. "1. Introduction", "2.3 Methods") and unnumbered label-like headings (e.g. "Specific Objectives").
3. Do NOT mark body sentences, captions (Figure/Table…), bullet/list items, or objective lines starting with "To …" as headings.
4. Do NOT invent paragraphs — only use paragraph_id values from the input.
5. Assign heading_level 1-4 (1 = top-level chapter, 2 = subsection, etc.).
6. Prefer structural reality over the template list. If a real heading is missing from the template, still include it.

Return ONLY valid JSON:
{{"headings": [
  {{"paragraph_id": "p0", "heading_level": 1, "confidence": 0.95}}
]}}

If none: {{"headings": []}}

Return ONLY the JSON object. No markdown, no explanation."""

        try:
            response = await client.messages.create(
                model=ANALYSIS_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            parsed = _safe_parse(raw)
            for item in parsed.get("headings") or []:
                if not isinstance(item, dict):
                    continue
                pid = str(item.get("paragraph_id") or "").strip()
                if not pid or pid in seen_pids:
                    continue
                try:
                    level = max(1, min(4, int(float(item.get("heading_level") or 1))))
                except (TypeError, ValueError):
                    level = 1
                try:
                    conf = float(item.get("confidence") if item.get("confidence") is not None else 0.85)
                except (TypeError, ValueError):
                    conf = 0.85
                conf = max(0.0, min(1.0, conf))
                seen_pids.add(pid)
                all_candidates.append({
                    "paragraph_id": pid,
                    "level": level,
                    "confidence": round(conf, 3),
                    "text": str(item.get("text") or ""),
                })
        except Exception as exc:
            print(f"[heading_detect] Claude batch error (non-fatal): {exc}")
            continue

    print(f"[heading_detect] Claude found {len(all_candidates)} heading candidate(s)")
    return all_candidates
