"""
functions/formatting.py — Formatting compliance checker.

Model: claude-haiku-4-5-20251001

Compares the document structure against the selected template by
injecting an EXPLICIT, per-heading-level rule block into the prompt,
built directly from the structured template (required_sections +
formatting_rules), rather than relying on a single free-text markdown
blob that the model has to parse and prioritize itself.

WHY THIS CHANGED
-----------------
The previous version injected `template.markdown_rules` (a pre-rendered
string) as-is. That string only gave explicit heading examples for
sections listed in `required_sections` — which are almost always
Heading 1 (top-level chapters). Heading 2/3 subsections rarely appear
in `required_sections`, so the model had no explicit instruction to
check them and, per its own rule #3 ("match the section name"), had
reason to skip anything not on that list. Result: Heading 1 got
audited, Heading 2/3 silently did not.

This version builds a dedicated "HEADING LEVEL RULES" block that:
  1. Documents every heading level that's either used in
     required_sections OR has explicit style rules in formatting_rules.
  2. Explicitly states each level's rule applies to ANY paragraph that
     functions as a section/subsection title at that level — not just
     ones whose text matches a required_sections entry.
  3. Instructs the model to audit every level independently instead of
     stopping after Level 1.

It also stops silently coercing a missing `heading_level` to `1`,
which was mislabeling/masking genuine Heading 2+ detections downstream.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Union

import anthropic

from models import Batch

# Import centralized model config — never hardcode the model string
from config import ANALYSIS_MODEL


# --------------------------------------------------------------------------
# Template -> explicit per-level heading rule block
# --------------------------------------------------------------------------

def _collect_heading_levels(required_sections: List[Any]) -> Dict[int, List[str]]:
    """Map heading_level -> list of known example section names at that level."""
    levels: Dict[int, List[str]] = {}
    for sec in required_sections or []:
        if isinstance(sec, dict):
            name = str(sec.get("name", "")).strip()
            level = int(sec.get("heading_level", 1) or 1)
        else:
            name, level = str(sec), 1
        level = max(1, min(4, level))
        if name:
            levels.setdefault(level, []).append(name)
    return levels


def _style_desc(rules: Dict[str, Any], prefix: str) -> str:
    if not any(k.startswith(prefix) for k in rules.keys()):
        return ""
    font = rules.get(f"{prefix}_font", "Times New Roman")
    size = rules.get(f"{prefix}_size", 12)
    bold = "Bold" if rules.get(f"{prefix}_bold", True) else "Regular"
    italic = "Italic" if rules.get(f"{prefix}_italic", False) else "Non-Italic"
    line_spacing = rules.get(f"{prefix}_line_spacing", 1.5)
    return f"{font}, {size}pt, {bold}, {italic}, Line Spacing {line_spacing}"


def _build_heading_rules_block(template: Dict[str, Any]) -> str:
    """
    Build an explicit, per-level heading instruction block from the
    structured template (not the pre-rendered markdown string).
    """
    required_sections = template.get("required_sections", []) or []
    rules = template.get("formatting_rules", {}) or {}
    levels_map = _collect_heading_levels(required_sections)

    lines: List[str] = []
    for level in (1, 2, 3, 4):
        prefix = f"heading{level}"
        style_desc = _style_desc(rules, prefix)
        examples = levels_map.get(level, [])

        # Include this level if it has either known examples or explicit
        # style rules. Skip only if the template genuinely never mentions it.
        if not examples and not style_desc:
            continue

        example_txt = (
            f" Known top-level examples of this level in this template: {', '.join(examples)}."
            if examples
            else " No fixed example list — identify candidates structurally (see rule below)."
        )
        style_txt = f" Required style: {style_desc}." if style_desc else ""

        lines.append(
            f"- HEADING LEVEL {level} → Word style 'Heading {level}'.{style_txt}{example_txt} "
            f"IMPORTANT: this rule applies to ANY paragraph that functions as a section/subsection "
            f"title at this level — whether or not its exact text appears in the required-sections "
            f"list above. Do not skip a paragraph just because its name isn't pre-listed."
        )

    if not lines:
        return "- No heading-level-specific rules configured for this template."

    return "\n".join(lines)


def _template_to_prompt_block(template: Union[str, Dict[str, Any]]) -> str:
    """
    Accepts either:
      - a full structured template dict (preferred — has required_sections
        and formatting_rules, enabling explicit per-level rules), or
      - a legacy pre-rendered markdown string (fallback, for callers not
        yet updated to pass the full dict).
    """
    if isinstance(template, dict):
        name = template.get("name", "Template")
        required_sections = template.get("required_sections", []) or []
        sections_text = "\n".join(
            f"- Section {idx + 1}: **{sec.get('name', sec) if isinstance(sec, dict) else sec}** "
            f"→ MUST use Word style **Heading {sec.get('heading_level', 1) if isinstance(sec, dict) else 1}**"
            for idx, sec in enumerate(required_sections)
        )
        heading_rules_block = _build_heading_rules_block(template)
        base_markdown = template.get("markdown_rules", "")

        return f"""# {name} — Formatting Specification

## Required Document Sections (strict order)
{sections_text}

## HEADING LEVEL RULES (check EVERY level independently — do not stop after Level 1)
{heading_rules_block}

## Additional template detail
{base_markdown}"""

    # Legacy string fallback — still add the "check every level" nudge,
    # since we can't build per-level examples from a raw string.
    return f"""{template}

## REMINDER — CHECK EVERY HEADING LEVEL INDEPENDENTLY
Do not stop after auditing Heading 1. Independently verify every paragraph
against Heading 2, Heading 3, and Heading 4 rules as well, including
subsection titles that are not explicitly named in the required-sections
list above. A document commonly has issues at multiple heading levels at
the same time — missing Heading 2+ violations is a critical failure."""


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
2. The "suggestion" field must describe WHAT TO DO (e.g. "Apply Heading 1 style") — NEVER put replacement paragraph text in suggestion.
3. Section titles MUST use Word style "Heading 1/2/3/4" — NOT just bold Normal text.
4. Every issue MUST reference an existing paragraph_id from the input.
5. For heading_style issues, you MUST include heading_level (1-4) — this is required, never omit it.
6. HEADINGS — BE CONSERVATIVE:
   - Emit heading_style ONLY when the paragraph is a true short section title AND its Word style is wrong.
   - Do NOT emit heading_style for: list items, "Label: description" rows, "To …" objectives, Figure/Table captions, or long body sentences.
   - Do NOT change a heading that is already the correct Heading 1–4 style.
   - Do NOT invent extra headings just to "improve" structure.
7. Use "heading_context" to understand hierarchy, but never promote list/body lines into headings.
8. LISTS — BE CONSERVATIVE:
   - Prefer confirming the high-confidence pre-pass.
   - For ambiguous candidates, confirm only true parallel lists (2+ consecutive sibling items with the same pattern).
   - Do NOT flag a single standalone descriptive paragraph as needing bullets.
   - Do NOT bullet architecture/prose paragraphs that merely contain a colon.
9. Prefer FEWER accurate issues over many false positives. False heading changes and false bullets are critical failures.

For each violation return:
- "paragraph_id": exact paragraph_id from input (required)
- "page": page number
- "type": one of heading_style, section_order, missing_section, font, spacing, alignment, margin, list_formatting
- "problem": what rule is violated (do NOT repeat paragraph text as a fix)
- "reason": same as problem — what is wrong structurally (for list_formatting, also name the sibling paragraph_ids in the same list group)
- "suggestion": instruction only (e.g. "Apply Heading 2 style to this subsection title" or "Convert this paragraph into a bulleted list item, grouped with paragraph_ids p12, p13, p14")
- "heading_level": integer 1-4 (REQUIRED when type is heading_style — do not omit; omit or set 0 for other types)
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
            suggestion = iss.get("suggestion", "") or iss.get("problem", "")
            reason = iss.get("reason", "") or iss.get("problem", "")
            pid = iss.get("paragraph_id", "")

            # Skip duplicate list_formatting already covered by the pre-pass
            if issue_type == "list_formatting" and pid in seen_list_pids:
                continue

            raw_level = iss.get("heading_level")
            if issue_type == "heading_style":
                if raw_level is None or raw_level == "":
                    print(
                        f"[formatting] WARNING: heading_style issue on "
                        f"paragraph_id={pid} missing heading_level "
                        f"from model output; defaulting to 1 as last resort."
                    )
                    heading_level = 1
                else:
                    heading_level = max(1, min(4, int(float(raw_level))))
                if not suggestion:
                    suggestion = f"Apply Heading {heading_level} style to this section title"
            else:
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