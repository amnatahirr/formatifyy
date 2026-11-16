"""
functions/formatting.py - Formatting compliance checker.

Model: claude-haiku-4-5-20251001

HEADING LEVELS ARE NO LONGER DECIDED HERE.
The single source of truth is the document-level outline built once by
functions/outline.py (functions/heading_resolver.py). This LLM audit only
checks font, spacing, alignment, margin and list formatting, and receives each
paragraph's `expected_heading_level` so heading font rules use the right level.
heading_style / section_order / missing_section issues are produced
deterministically by outline_to_issues() and any such issue the LLM returns is
discarded.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Union

import anthropic

from models import Batch

# Import centralized model config — never hardcode the model string
from config import ANALYSIS_MODEL


# --------------------------------------------------------------------------
# Template -> prompt block (no heading-level rules: see module docstring)
# --------------------------------------------------------------------------

def _template_to_prompt_block(template: Union[str, Dict[str, Any]]) -> str:
    """Accepts the structured template dict or a legacy markdown string."""
    if isinstance(template, dict):
        name = template.get("name", "Template")
        base_markdown = template.get("markdown_rules", "")
        return f"# {name} - Formatting Specification\n\n{base_markdown}"
    return str(template)


# --------------------------------------------------------------------------
# Main check
# --------------------------------------------------------------------------

_SAFE_LIST_DETECTIONS = frozenset({
    "infinitive",
    "gerund",
    "trigger_line",
    "trigger_follower",
    "marker",
    "bullet_marker",
})


async def check_formatting(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
    template: Union[str, Dict[str, Any]],
    outline: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Compare batch paragraphs against the template rules.

    High-confidence list patterns (infinitives / markers / trigger lines) are
    seeded deterministically. Ambiguous "Label: description" groups are sent to
    the LLM as candidates — the agent must confirm before they become issues.

    `template` should ideally be the full structured template dict returned
    by templates.get_template_by_id() / get_all_templates() (i.e. containing
    required_sections + formatting_rules), not just template["markdown_rules"].
    Passing the full dict is what enables explicit per-level heading checks.
    A plain markdown string is still accepted for backward compatibility.

    Returns a list of raw issue dicts plus a compliance_score.
    """
    if not batch.paragraphs:
        return []

    # ── Deterministic list pre-pass (before LLM) ─────────────────────────────
    from docx_tools.list_detection import (
        build_list_hint_payload,
        detect_list_groups,
        list_groups_to_issues,
    )

    list_groups = detect_list_groups(batch.paragraphs)
    confirmed_groups = [
        g for g in list_groups
        if (g.detection or "").lower() in _SAFE_LIST_DETECTIONS
    ]
    candidate_groups = [
        g for g in list_groups
        if (g.detection or "").lower() not in _SAFE_LIST_DETECTIONS
    ]

    # Only auto-seed high-confidence list patterns; Label:colon etc. need agent confirm
    deterministic_list_issues = list_groups_to_issues(
        confirmed_groups, issue_prefix="list_prepass"
    )
    list_hints = build_list_hint_payload(confirmed_groups)
    candidate_hints = build_list_hint_payload(candidate_groups)
    # Soften candidate hint instructions for the agent
    for h in candidate_hints:
        h["confidence"] = "candidate_only"
        h["instruction"] = (
            "CANDIDATE only (often false positive on PDF/architecture prose). "
            "Confirm as list_formatting ONLY if these are true parallel feature/"
            "objective items under a list intent. Otherwise IGNORE — do not bullet "
            "ordinary 'Label: explanation' body sentences."
        )

    preconfirmed_pids = {
        pid
        for g in confirmed_groups
        for pid in g.paragraph_ids
    }
    if list_groups:
        print(
            f"[formatting] list pre-pass: {len(confirmed_groups)} confirmed, "
            f"{len(candidate_groups)} candidate group(s)"
        )

    lvl_by_pid = {
        r.paragraph_id: r.expected_level
        for r in (outline or {}).get("headings", [])
    }
    paragraphs_payload = [
        {
            "paragraph_id": p.paragraph_id,
            "page": p.page_number,
            "style": p.style,
            "heading_context": p.heading_context,
            "text": p.text[:400],
            "preconfirmed_list_item": p.paragraph_id in preconfirmed_pids,
            "expected_heading_level": lvl_by_pid.get(p.paragraph_id),
        }
        for p in batch.paragraphs
    ]

    template_block = _template_to_prompt_block(template)
    list_hint_block = (
        json.dumps(list_hints, indent=2)
        if list_hints
        else "[]  (no high-confidence list groups in this batch)"
    )
    candidate_hint_block = (
        json.dumps(candidate_hints, indent=2)
        if candidate_hints
        else "[]"
    )

    prompt = f"""You are a strict academic document formatting auditor. Compare each paragraph against the template specification below.

TEMPLATE SPECIFICATION (authoritative — every rule must be enforced):
{template_block}

DOCUMENT PARAGRAPHS (from the student's file):
{json.dumps(paragraphs_payload, indent=2)}

HIGH-CONFIDENCE LIST PRE-PASS (authoritative — do NOT reject these):
{list_hint_block}
Paragraphs marked "preconfirmed_list_item": true are confirmed list members
(infinitives / explicit markers / trigger-line followers). Keep them as list_formatting.

AMBIGUOUS LIST CANDIDATES (agent must confirm or reject):
{candidate_hint_block}
These are often FALSE POSITIVES on PDF-converted text and architecture/module
descriptions like "Frontend (App): Students use…" or "Database (PostgreSQL): It holds…".
Only emit list_formatting for a candidate group if it is clearly a parallel bullet
list of features/objectives. Otherwise IGNORE — leave as Normal body text.

AUDIT RULES:
1. You must NEVER rewrite, summarize, or replace paragraph content. Only identify structural issues. The original text is sacred.
2. The "suggestion" field must describe WHAT TO DO (e.g. "Apply bulleted list formatting") - NEVER put replacement paragraph text in suggestion.
3. Every issue MUST reference an existing paragraph_id from the input.
4. HEADING LEVELS ARE ALREADY RESOLVED. Do NOT report heading_style, section_order or missing_section issues - they are handled elsewhere and will be discarded. Paragraphs with a non-null "expected_heading_level" are headings: apply that level's font/size/spacing rules to them (font, spacing, alignment issues only).
5. LISTS - BE CONSERVATIVE:
   - Prefer confirming the high-confidence pre-pass.
   - For ambiguous candidates, confirm only true parallel lists (2+ consecutive sibling items with the same pattern).
   - Do NOT flag a single standalone descriptive paragraph as needing bullets.
   - Do NOT bullet architecture/prose paragraphs that merely contain a colon.
6. Prefer FEWER accurate issues over many false positives. False bullets are critical failures.

For each violation return:
- "paragraph_id": exact paragraph_id from input (required)
- "page": page number
- "type": one of font, spacing, alignment, margin, list_formatting
- "problem": what rule is violated (do NOT repeat paragraph text as a fix)
- "reason": same as problem - what is wrong structurally (for list_formatting, also name the sibling paragraph_ids in the same list group)
- "suggestion": instruction only (e.g. "Convert this paragraph into a bulleted list item, grouped with paragraph_ids p12, p13, p14")
- "original": copy of paragraph text exactly as-is
- "severity": "major" or "minor" (list_formatting is typically "minor" unless it significantly hurts readability)

Return ONLY valid JSON:
{{"issues": [...], "compliance_score": 72, "summary": "Document is 72% compliant with template"}}

If no issues: {{"issues": [], "compliance_score": 100, "summary": "Fully compliant"}}

Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the raw JSON."""

    try:
        response = await client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        parsed = _safe_parse(raw)
        issues = parsed.get("issues", [])
        compliance_score = parsed.get("compliance_score", 100)

        result = []
        seen_list_pids: set = set()

        # Seed with deterministic list issues so detection never depends on the LLM
        for det in deterministic_list_issues:
            pid = det.get("paragraph_id", "")
            if det.get("type") == "list_formatting" and pid:
                seen_list_pids.add(pid)
            result.append({
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
                "current_heading": "",
                "content_belongs_to": "",
                "text_preview": (det.get("original") or det.get("reason") or "")[:120],
                "verdict": "",
                "confidence": int(float(compliance_score or 0)),
                "source": "list_detection_prepass",
                "list_detection": det.get("list_detection", ""),
                "para_indices": det.get("para_indices") or [],
                "fix_type": det.get("fix_type"),
                "fix_details": det.get("fix_details"),
                "issue_id": det.get("issue_id"),
                "_compliance_score": int(float(compliance_score or 0)),
            })

        for iss in issues:
            issue_type = iss.get("type", "formatting")
            if issue_type in ("heading_style", "section_order", "missing_section"):
                continue  # resolved deterministically by functions/outline.py
            suggestion = iss.get("suggestion", "") or iss.get("problem", "")
            reason = iss.get("reason", "") or iss.get("problem", "")
            pid = iss.get("paragraph_id", "")

            # Skip duplicate list_formatting already covered by the pre-pass
            if issue_type == "list_formatting" and pid in seen_list_pids:
                continue

            heading_level = 0

            if issue_type == "list_formatting" and pid:
                seen_list_pids.add(pid)

            result.append({
                "function": "formatting",
                "type": issue_type,
                "severity": iss.get("severity", "minor"),
                "paragraph_id": pid,
                "image_id": "",
                "page": iss.get("page", 0),
                "reason": reason,
                "suggestion": suggestion,
                "explanation": reason,
                "original": iss.get("original", ""),
                "heading_level": heading_level,
                "current_heading": "",
                "content_belongs_to": "",
                "text_preview": (iss.get("original") or "")[:120],
                "verdict": "",
                "confidence": int(float(compliance_score or 0)),
                "source": "llm_formatting",
                "_compliance_score": int(float(compliance_score or 0)),
            })
        return result
    except Exception as exc:
        print(f"[formatting] error: {exc}")
        # Still return deterministic list findings if the LLM call fails
        fallback = []
        for det in deterministic_list_issues:
            if det.get("type") != "list_formatting":
                continue
            fallback.append({
                "function": "formatting",
                "type": "list_formatting",
                "severity": "minor",
                "paragraph_id": det.get("paragraph_id", ""),
                "page": 0,
                "reason": det.get("reason", ""),
                "suggestion": det.get("suggestion", ""),
                "original": det.get("original", ""),
                "heading_level": 0,
                "source": "list_detection_prepass",
                "list_detection": det.get("list_detection", ""),
                "para_indices": det.get("para_indices") or [],
            })
        return fallback


def _safe_parse(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"issues": [], "error": True}