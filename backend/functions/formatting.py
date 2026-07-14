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

async def check_formatting(
    client: anthropic.AsyncAnthropic,
    batch: Batch,
    template: Union[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Compare batch paragraphs against the template rules.

    List detection is done deterministically FIRST (label:colon, parallel
    infinitive/gerund/marker runs, trigger lines). The LLM only confirms /
    assigns list level — it does not decide whether something is a list.

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
    from list_detection import (
        build_list_hint_payload,
        detect_list_groups,
        list_groups_to_issues,
    )

    list_groups = detect_list_groups(batch.paragraphs)
    deterministic_list_issues = list_groups_to_issues(
        list_groups, issue_prefix="list_prepass"
    )
    list_hints = build_list_hint_payload(list_groups)
    preconfirmed_pids = {
        pid
        for g in list_groups
        for pid in g.paragraph_ids
    }
    if list_groups:
        print(
            f"[formatting] list pre-pass: {len(list_groups)} group(s), "
            f"{len(preconfirmed_pids)} paragraphs confirmed as list items"
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
        else "[]  (no deterministic list groups in this batch)"
    )

    prompt = f"""You are a strict academic document formatting auditor. Compare each paragraph against the template specification below.

TEMPLATE SPECIFICATION (authoritative — every rule must be enforced):
{template_block}

DOCUMENT PARAGRAPHS (from the student's file):
{json.dumps(paragraphs_payload, indent=2)}

DETERMINISTIC LIST PRE-PASS (authoritative — do NOT second-guess these):
{list_hint_block}
Paragraphs marked "preconfirmed_list_item": true are already confirmed list
members. For those, only emit list_formatting if useful for the UI — do not
argue they are body text. Focus your own list discovery on OTHER paragraphs
not covered by the pre-pass.

AUDIT RULES:
1. You must NEVER rewrite, summarize, or replace paragraph content. Only identify structural issues. The original text is sacred.
2. The "suggestion" field must describe WHAT TO DO (e.g. "Apply Heading 1 style") — NEVER put replacement paragraph text in suggestion.
3. Section titles MUST use Word style "Heading 1/2/3/4" — NOT just bold Normal text.
4. Every issue MUST reference an existing paragraph_id from the input.
5. For heading_style issues, you MUST include heading_level (1-4) — this is required, never omit it.
6. CHECK EVERY HEADING LEVEL INDEPENDENTLY. A paragraph that functions as a subsection title (short, standalone, distinct from surrounding body text, introduces a topic followed by body paragraphs) must be checked against its level's rule EVEN IF its exact text is not in the required-sections list. Do not limit heading_style checks to Heading 1 only. Structurally obvious labels under a numbered heading (e.g. "Specific Objectives" under "2.6.1 Main Goal") are Heading 3 candidates.
7. Use the "heading_context" field of each paragraph to understand its position in the document hierarchy (e.g. a paragraph whose heading_context shows it sits under "1. Introduction" as a subsection is a Heading 2 candidate).
8. CHECK FOR CONTENT THAT SHOULD BE A BULLETED/NUMBERED LIST but is currently written as plain running paragraphs. Prefer confirming the deterministic pre-pass. Additionally look for:
   - A repeating "Label: description" or "Bold Term — explanation" pattern.
   - Parallel infinitive items ("To develop…", "To build…", "To implement…") or gerunds after a trigger line ending in "are:" / "include:" / "as follows:".
   - Manual markers (-, *, •, a), i), 1.).
   When you detect this pattern, flag EACH paragraph in that group individually with type "list_formatting" — note sibling paragraph_ids in "reason".
   Do NOT flag a single standalone descriptive paragraph as needing bullets — only flag when there is a real repeating parallel-item pattern across 2+ consecutive paragraphs.

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