"""
functions/outline.py — builds the ONE document-level heading outline.

Call build_outline() once per document (never per batch), then:
  * pass `outline` to dispatch_all(...) so formatting.py can show expected levels
  * call outline_to_issues(outline, doc) once and add the result to raw_issues
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from functions.heading_text import detect_heading_candidates
from functions.heading_resolver import resolve_headings, style_level


async def build_outline(
    client: Any,
    doc: Any,
    template: Optional[Dict[str, Any]],
    decisions: Optional[Dict[str, str]] = None,
    skip_pids=frozenset(),
) -> Dict[str, Any]:
    """
    doc       : DocumentModel (frontmatter already stripped by the caller)
    decisions : {paragraph_id: "keep" | "discard"} user overrides
                (main._load_heading_decisions)
    """
    decisions = decisions or {}
    blocks = doc.paragraphs
    is_docx = (doc.filename or "").lower().endswith(".docx")
    used = {style_level(b.style_name) for b in blocks if style_level(b.style_name)}
    # PDF/TXT styles are guesses; DOCX styles only help if the author used >1 level
    styles_informative = is_docx and len(used) >= 2

    try:
        llm = {
            c["paragraph_id"]: c
            for c in await detect_heading_candidates(client, blocks, template)
        }
    except Exception as exc:
        print(f"[outline] heading detection failed, using styles only: {exc}")
        llm = {}

    cands = []
    for b in blocks:
        pid, text = b.paragraph_id, (b.text or "").strip()
        if not text or pid in skip_pids or decisions.get(pid) == "discard":
            continue
        lvl = style_level(b.style_name)
        c = llm.get(pid)
        forced = decisions.get(pid) == "keep"
        if not (lvl or c or forced):
            continue
        hint = lvl if (styles_informative and lvl) else (c or {}).get("level")
        cands.append({
            "paragraph_id": pid, "text": text,
            "style": b.style_name or "", "hint_level": hint,
        })

    outline = resolve_headings(cands, (template or {}).get("required_sections"))
    print(
        f"[outline] {len(outline['headings'])} headings, "
        f"{len(outline['changes'])} level changes, "
        f"{len(outline['list_items'])} list items, "
        f"{len(outline['missing_sections'])} missing, "
        f"{len(outline['needs_review'])} need review"
    )
    return outline


def outline_to_issues(outline: Dict[str, Any], doc: Any) -> list:
    """heading_style + list issues. (missing_section is handled by missing_sections.py)"""
    page = {p.paragraph_id: p.page_number for p in doc.paragraphs}
    base = {"function": "formatting", "image_id": "", "current_heading": "",
            "content_belongs_to": "", "verdict": "", "source": "heading_resolver"}
    issues = []
    for r in outline["changes"]:
        issues.append({
            **base, "type": "heading_style",
            "severity": "minor" if r.needs_review else "major",
            "paragraph_id": r.paragraph_id, "page": page.get(r.paragraph_id, 0),
            "reason": f"Template expects Heading {r.expected_level} ({r.reason})",
            "suggestion": f"Apply Heading {r.expected_level} style",
            "explanation": r.reason, "original": r.text, "text_preview": r.text[:120],
            "heading_level": r.expected_level,
            "matched_template_heading": r.template_name or None,
            "confidence": int(r.confidence * 100), "needs_review": r.needs_review,
        })
    for r in outline["list_items"]:
        if r.current_level is None:  # only items wrongly styled as headings
            continue
        issues.append({
            **base, "type": "list_formatting", "severity": "major",
            "paragraph_id": r.paragraph_id, "page": page.get(r.paragraph_id, 0),
            "reason": "List item wrongly styled as a heading",
            "suggestion": "Remove heading style and convert to a list item",
            "explanation": r.reason, "original": r.text, "text_preview": r.text[:120],
            "heading_level": 0, "confidence": 90,
        })
    if issues:
        n = max(1, len(outline["headings"]))
        issues[0]["_compliance_score"] = round(100 * (1 - len(outline["changes"]) / n))
    return issues