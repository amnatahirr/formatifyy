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
    has_outline = bool(section_names)
    outline_hint = (
        json.dumps(section_names, indent=2)
        if has_outline
        else "[]  (EMPTY — no required_sections; YOU must decide Heading 1 vs 2 vs 3 by document structure)"
    )

    if has_outline:
        level_rules = """5. Assign heading_level 1-4 from STRUCTURE + reliable numbering:
   - "1." / "2." / "Chapter 1" → level 1
   - "1.1" / "2.3" → level 2
   - "1.1.1" → level 3
   Prefer numbering depth when it starts at 1 (not 0).
6. Prefer structural reality over the template list. If a real heading is missing from the template, still include it.
7. NEVER mark these as headings (even if short or Title Case):
   - Bullet / numbered list items ("• …", "- …", "1. Feature: description", "a) …")
   - "Label: long description" feature/module rows (e.g. "Admin Panel: It allows…", "Frontend (App): Students use…")
   - Parallel objectives starting with "To develop/build/implement…"
   - Figure/Table captions ("Figure 1: …", "Table 2: …")
   - Full sentences of body prose (multiple clauses, ends with period, > ~12 words)
8. Be CONSERVATIVE. If unsure whether something is a heading or a list/body line, OMIT it from headings."""
    else:
        level_rules = """5. THIS TEMPLATE HAS NO SECTIONS DEFINED. You MUST invent the outline:
   Decide heading_level from ROLE in the document, NOT from broken numbers like "0.1".
   - Level 1 = major sections / chapters (Abstract, Introduction, Literature Review,
     Methodology, Results, Discussion, Conclusion, References, Appendices, etc.)
   - Level 2 = subsections under a major section (e.g. under Introduction: Problem Statement,
     Objectives, Scope)
   - Level 3 = sub-subsections under a level-2 heading
   Correct conceptual numbering is 1, then 1.1 / 1.2, then 2, 2.1 — NEVER start at 0.1.
   If text says "0.1. Abstract" or "0.1 Abstract", still assign heading_level 1 (Abstract is major).
   If text says "0.1.1 Something" under Abstract, assign level 2 (first subsection), not level 3 from digits.
6. Ignore zero-based prefixes ("0", "0.1", "0.1.2") when choosing level — treat them as typos.
7. Prefer title meaning + order: first major title → level 1; following nested titles → level 2/3.
8. NEVER mark these as headings:
   - Bullet / numbered list items, "To …" objectives, Figure/Table captions
   - "Label: description" feature rows (Admin Panel / Backend / Database / Module lines)
   - Long body sentences
9. Be CONSERVATIVE. When unsure, OMIT — false headings are worse than a missed one."""

    all_candidates: List[Dict[str, Any]] = []
    seen_pids: set[str] = set()

    for start in range(0, len(payload), _BATCH_SIZE):
        chunk = payload[start : start + _BATCH_SIZE]
        prompt = f"""You are an expert academic document structure analyzer.
Identify ONLY paragraphs that are true section / subsection HEADINGS (titles), not body or list text.

TEMPLATE SECTION NAMES:
{outline_hint}

PARAGRAPHS:
{json.dumps(chunk, indent=2)}

RULES:
1. A heading is a short standalone TITLE that names a section (usually ≤ 10 words, not a full sentence).
2. Include real numbered headings (e.g. "1. Introduction", "2.3 Methods") and short unnumbered section labels (e.g. "Specific Objectives", "Abstract").
3. Do NOT mark body sentences, captions (Figure/Table…), bullet/list items, "Label: description" rows, or objective lines starting with "To …" as headings.
4. Do NOT invent paragraphs — only use paragraph_id values from the input.
5. Do NOT "fix" or rewrite numbering in the output — only report paragraph_id + heading_level.
{level_rules}

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
