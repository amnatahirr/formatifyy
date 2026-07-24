"""
functions/frontmatter_classify.py — LLM fallback for frontmatter page detection.

Called only when heuristic confidence is ambiguous. Returns a JSON-shaped dict:
  cover_page_present, info_page_present, confidence, reasoning
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from config import ANALYSIS_MODEL


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text or "").strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"error": True}


def _page_summary(paras: List[Dict[str, Any]], max_chars: int = 2500) -> str:
    lines: List[str] = []
    used = 0
    for p in paras:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        style = p.get("style") or "Normal"
        align = p.get("alignment") or "left"
        size = p.get("font_size")
        size_s = f"{size:.0f}pt" if isinstance(size, (int, float)) else "?"
        has_img = "yes" if p.get("has_image") else "no"
        line = f"[{style}|{align}|{size_s}|img={has_img}] {text[:220]}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines) if lines else "(empty)"


async def classify_frontmatter_with_llm(
    client: Any,
    page1_paras: List[Dict[str, Any]],
    page2_paras: List[Dict[str, Any]],
    heuristic_hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ask the analysis LLM whether page 1 is a cover and page 2 is a project-details page.

    Returns:
      {
        cover_page_present: bool,
        info_page_present: bool,
        confidence: float,
        reasoning: str,
      }
    """
    if client is None:
        return {
            "cover_page_present": False,
            "info_page_present": False,
            "confidence": 0.0,
            "reasoning": "No LLM client available.",
            "error": True,
        }

    hints = json.dumps(heuristic_hints or {}, indent=2)
    prompt = f"""You classify the first two pages of a student FYP report (DOCX layout summary).

Decide INDEPENDENTLY:
1) Is PAGE 1 a COVER / TITLE page?
   Signals: large centered title, university name, logo/image, little body prose.
2) Is PAGE 2 a PROJECT DETAILS / INFO page?
   Signals: table or label:value rows (Group Members, Supervisor, Registration No),
   names/reg numbers, domain checkboxes.

HEURISTIC PRE-CHECK (hints only — you may override):
{hints}

PAGE 1 PARAGRAPHS:
{_page_summary(page1_paras)}

PAGE 2 PARAGRAPHS:
{_page_summary(page2_paras)}

Return ONLY valid JSON:
{{
  "cover_page_present": true,
  "info_page_present": false,
  "confidence": 0.82,
  "reasoning": "short explanation"
}}

confidence is 0.0-1.0 for your overall judgment.
Return ONLY the JSON object. No markdown."""

    try:
        response = await client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = ""
        if getattr(response, "content", None):
            raw = getattr(response.content[0], "text", "") or ""
        parsed = _safe_parse(raw)
        if parsed.get("error"):
            return {
                "cover_page_present": False,
                "info_page_present": False,
                "confidence": 0.0,
                "reasoning": "LLM returned unparseable JSON.",
                "error": True,
            }
        return {
            "cover_page_present": bool(parsed.get("cover_page_present")),
            "info_page_present": bool(parsed.get("info_page_present")),
            "confidence": float(parsed.get("confidence") or 0.0),
            "reasoning": str(parsed.get("reasoning") or "").strip(),
        }
    except Exception as exc:
        print(f"[frontmatter_classify] LLM error: {exc}")
        return {
            "cover_page_present": False,
            "info_page_present": False,
            "confidence": 0.0,
            "reasoning": f"LLM call failed: {exc}",
            "error": True,
        }
