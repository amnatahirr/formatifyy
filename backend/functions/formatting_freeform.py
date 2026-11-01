"""
functions/formatting_freeform.py — Template-free formatting checker.

Uses the same Anthropic client / ANALYSIS_MODEL pattern as formatting.py,
but with a general academic prompt (no required_sections / template rules).

Issue types intentionally exclude section_order and missing_section
(those require a template). Citation issues go to suggested_manual_notes only.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import anthropic

from models import Batch
from config import ANALYSIS_MODEL

# Ceiling of what reformat_document() can apply (wholesale style pass).
ALLOWED_FIX_ACTIONS = frozenset(
    {
        "apply_heading_style",
        "apply_body_font",
        "apply_body_spacing",
        "apply_alignment",
        "apply_page_margins",
    }
)

ALLOWED_ISSUE_TYPES = frozenset(
    {
        "heading_style",
        "font",
        "spacing",
        "alignment",
        "margin",
        "list_formatting",
    }
)


def _safe_parse(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def check_formatting_freeform(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """
    General academic formatting audit (no org template).

    Returns issue dicts compatible with the template formatting path, plus
    attaches `_suggested_fixes` / `_suggested_manual_notes` / `_compliance_score`
    on a synthetic summary issue when present (merged in freeform runner).
    """
    if not batch.paragraphs:
        return []

    from docx_tools.list_detection import (
        build_list_hint_payload,
        detect_list_groups,
        list_groups_to_issues,
    )

    _SAFE = {
        "infinitive",
        "gerund",
        "trigger_line",
        "trigger_follower",
        "marker",
        "bullet_marker",
    }
    list_groups = detect_list_groups(batch.paragraphs)
    confirmed = [g for g in list_groups if (g.detection or "").lower() in _SAFE]
    candidates = [g for g in list_groups if (g.detection or "").lower() not in _SAFE]
    deterministic_list_issues = list_groups_to_issues(
        confirmed, issue_prefix="list_prepass_freeform"
    )
    list_hints = build_list_hint_payload(confirmed)
    candidate_hints = build_list_hint_payload(candidates)
    for h in candidate_hints:
        h["confidence"] = "candidate_only"
        h["instruction"] = (
            "CANDIDATE only — confirm list_formatting only for true parallel "
            "feature/objective lists; ignore ordinary Label: prose."
        )
    preconfirmed_pids = {
        pid for g in confirmed for pid in g.paragraph_ids
    }

    paragraphs_payload = [
        {
            "paragraph_id": p.paragraph_id,
            "page": p.page_number,
            "style": p.style,
            "heading_context": p.heading_context,
            "text": p.text[:400],
            "preconfirmed_list_item": p.paragraph_id in preconfirmed_pids,
        }
        for p in batch.paragraphs
    ]

    list_hint_block = (
        json.dumps(list_hints, indent=2)
        if list_hints
        else "[]  (no high-confidence list groups in this batch)"
    )
    candidate_hint_block = (
        json.dumps(candidate_hints, indent=2) if candidate_hints else "[]"
    )

    prompt = f"""You are a strict academic document formatting auditor. There is NO organization
template. Apply only general academic formatting guidelines.

DOCUMENT PARAGRAPHS:
{json.dumps(paragraphs_payload, indent=2)}

HIGH-CONFIDENCE LIST PRE-PASS (authoritative — do NOT reject these):
{list_hint_block}
Paragraphs marked "preconfirmed_list_item": true are confirmed list members.

AMBIGUOUS LIST CANDIDATES (confirm or reject):
{candidate_hint_block}
Ignore false-positive Label: architecture/module prose unless it is a true parallel list.

GUIDELINES (authoritative for this run):
1. NEVER rewrite, summarize, or replace paragraph content. Only identify structural issues.
2. "suggestion" must describe WHAT TO DO — never put replacement paragraph text in suggestion.
3. Section / subsection titles should use Word Heading 1–4 styles, not bold Normal text.
4. Prefer consistent body font/size, line spacing, and alignment across body paragraphs.
5. Flag inconsistent page margins only if clearly wrong for academic work (typical ~1" / 25mm).
6. Citation-pattern issues (mixed author-year vs numbered styles, inconsistent citation
   formatting) must ALWAYS go into suggested_manual_notes — never into issues[].
7. Every issue MUST reference an existing paragraph_id from the input.
8. For heading_style issues, include heading_level (1-4). Be CONSERVATIVE: only true short
   section titles with wrong style — never list items, Label: rows, captions, or long prose.
9. Only emit auto-applicable fix hints using the allowed fix_action values listed below.
   If a finding cannot be expressed as an allowed fix_action, put it in suggested_manual_notes
   instead (or set auto_applicable=false).
10. Do NOT use issue types section_order or missing_section — there is no template section list.
11. Prefer fewer accurate issues over many false heading/bullet changes.

ALLOWED issue type values: heading_style, font, spacing, alignment, margin, list_formatting

ALLOWED fix_action values (auto-apply ceiling — matches reformat_document capabilities):
- apply_heading_style (requires heading_level 1-4)
- apply_body_font
- apply_body_spacing
- apply_alignment
- apply_page_margins
Anything else is NOT auto-applicable.

Return ONLY valid JSON (no markdown/fences):
{{
  "issues": [
    {{
      "paragraph_id": "p12",
      "page": 1,
      "type": "heading_style",
      "problem": "...",
      "reason": "...",
      "suggestion": "...",
      "heading_level": 2,
      "original": "...",
      "severity": "major"
    }}
  ],
  "suggested_fixes": [
    {{
      "paragraph_id": "p12",
      "type": "heading_style",
      "fix_action": "apply_heading_style",
      "heading_level": 2,
      "auto_applicable": true,
      "suggestion": "Apply Heading 2 style"
    }}
  ],
  "suggested_manual_notes": [
    {{ "paragraph_id": "p40", "note": "..." }}
  ],
  "compliance_score": 72,
  "summary": "…"
}}

If no issues: {{"issues": [], "suggested_fixes": [], "suggested_manual_notes": [], "compliance_score": 100, "summary": "Fully compliant with general academic guidelines"}}"""

    try:
        response = await client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        parsed = _safe_parse(raw)
    except Exception as exc:
        print(f"[formatting_freeform] LLM call failed: {exc}")
        return []

    issues = parsed.get("issues", []) or []
    compliance_score = parsed.get("compliance_score", 100)
    suggested_fixes = parsed.get("suggested_fixes", []) or []
    manual_notes = parsed.get("suggested_manual_notes", []) or []

    # Normalize / filter suggested fixes to allowed actions only
    clean_fixes: List[Dict[str, Any]] = []
    for fix in suggested_fixes:
        if not isinstance(fix, dict):
            continue
        action = str(fix.get("fix_action") or "").strip()
        auto = bool(fix.get("auto_applicable", True))
        if action not in ALLOWED_FIX_ACTIONS:
            auto = False
            note = {
                "paragraph_id": fix.get("paragraph_id", ""),
                "note": fix.get("suggestion")
                or f"Suggested fix '{action}' is not auto-applicable.",
            }
            manual_notes.append(note)
            continue
        clean_fixes.append(
            {
                "paragraph_id": str(fix.get("paragraph_id") or ""),
                "type": str(fix.get("type") or "formatting"),
                "fix_action": action,
                "heading_level": int(fix.get("heading_level") or 0),
                "auto_applicable": auto,
                "suggestion": str(fix.get("suggestion") or ""),
            }
        )

    result: List[Dict[str, Any]] = []
    seen_list_pids: set = set()

    for det in deterministic_list_issues:
        pid = det.get("paragraph_id", "")
        if det.get("type") == "list_formatting" and pid:
            seen_list_pids.add(pid)
        result.append(
            {
                "function": "formatting",
                "type": det.get("type", "list_formatting"),
                "severity": det.get("severity", "minor"),
                "paragraph_id": pid,
                "image_id": "",
                "page": 0,
                "reason": det.get("reason", ""),
                "suggestion": det.get("suggestion", ""),
                "explanation": det.get("reason", ""),
                "original": det.get("original", ""),
                "heading_level": 0,
                "text_preview": (det.get("original") or det.get("reason") or "")[:120],
                "confidence": int(float(compliance_score or 0)),
                "source": "list_detection_prepass",
                "auto_applicable": False,  # list bullets outside reformat_document
                "_compliance_score": int(float(compliance_score or 0)),
            }
        )

    for iss in issues:
        if not isinstance(iss, dict):
            continue
        issue_type = str(iss.get("type") or "formatting")
        if issue_type in ("section_order", "missing_section"):
            continue
        if issue_type not in ALLOWED_ISSUE_TYPES:
            # Force unknown types into manual notes
            manual_notes.append(
                {
                    "paragraph_id": iss.get("paragraph_id", ""),
                    "note": iss.get("suggestion")
                    or iss.get("problem")
                    or f"Unsupported issue type: {issue_type}",
                }
            )
            continue

        pid = iss.get("paragraph_id", "")
        if issue_type == "list_formatting" and pid in seen_list_pids:
            continue

        raw_level = iss.get("heading_level")
        heading_level = 0
        if issue_type == "heading_style":
            try:
                heading_level = int(raw_level or 0)
            except (TypeError, ValueError):
                heading_level = 0

        result.append(
            {
                "function": "formatting",
                "type": issue_type,
                "severity": iss.get("severity", "minor"),
                "paragraph_id": pid,
                "image_id": "",
                "page": iss.get("page", 0),
                "reason": iss.get("reason") or iss.get("problem") or "",
                "suggestion": iss.get("suggestion") or iss.get("problem") or "",
                "explanation": iss.get("reason") or iss.get("problem") or "",
                "original": iss.get("original", ""),
                "heading_level": heading_level,
                "text_preview": (iss.get("original") or "")[:120],
                "confidence": int(float(compliance_score or 0)),
                "source": "formatting_freeform",
                "_compliance_score": int(float(compliance_score or 0)),
            }
        )

    # Attach freeform metadata once (picked up by analyze-freeform aggregator)
    if result:
        result[0]["_suggested_fixes"] = clean_fixes
        result[0]["_suggested_manual_notes"] = manual_notes
        result[0]["_freeform_summary"] = parsed.get("summary", "")
    elif clean_fixes or manual_notes:
        result.append(
            {
                "function": "formatting",
                "type": "summary",
                "severity": "minor",
                "paragraph_id": "",
                "reason": parsed.get("summary", "Freeform analysis complete"),
                "suggestion": "",
                "source": "formatting_freeform",
                "_suggested_fixes": clean_fixes,
                "_suggested_manual_notes": manual_notes,
                "_freeform_summary": parsed.get("summary", ""),
                "_compliance_score": int(float(compliance_score or 0)),
            }
        )

    return result
