"""
missing_sections.py - whole-document missing-section detection for Formatify.

Compares the template's required_sections against the headings that really
exist in the student's (working copy) DOCX. Runs on the WHOLE document at
once, so a section on page 20 is never reported missing just because it was
not inside the 4-page batch an LLM agent happened to see. No LLM needed.

Public functions
----------------
detect_missing_sections(docx_path, required_sections, max_level=None) -> dict
missing_sections_to_issues(missing) -> list[dict]      (issue dicts for the UI)
insert_missing_section_by_name(docx_path, required_sections, name) -> dict
collect_candidate_headings(docx_path) -> list[dict]
"""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

MATCH_THRESHOLD = 0.82
MIN_HEADINGS_FOR_RELIABLE = 2

_STOP = {"and", "of", "the", "a", "an", "for", "in", "on", "to"}

# In-memory cache for AI suggestions: (document_id, section_name, doc_hash) -> suggested_content
_SUGGESTION_CACHE: Dict[tuple, str] = {}

# Headings in the same group count as the same section. Extend freely.
_SYNONYM_GROUPS = [
    {"abstract"},
    {"introduction"},
    {"literature review", "related work", "related works", "literature survey",
     "review of literature", "background and related work"},
    {"methodology", "methods", "method", "proposed methodology",
     "research methodology", "materials and methods"},
    {"results", "findings", "results and analysis", "experimental results",
     "results and discussion"},
    {"discussion", "analysis and discussion"},
    {"conclusion", "conclusions", "concluding remarks",
     "conclusion and future work", "conclusions and future work"},
    {"references", "bibliography", "works cited", "reference list"},
    {"acknowledgements", "acknowledgments", "acknowledgement", "acknowledgment"},
    {"table of contents", "contents"},
    {"list of figures", "table of figures", "list of images"},
    {"list of tables"},
    {"appendix", "appendices"},
    {"problem statement", "statement of the problem"},
    {"objectives", "project objectives", "aims and objectives"},
    {"tools and technologies", "technologies used", "tools and technology"},
]

_PREFIXES = [
    re.compile(r"^(?:chapter|section)\s+\d+\s*[:.\-\u2013]?\s*", re.I),
    re.compile(r"^\d+(?:\.\d+)+[.)]?\s*(?=\S)"),
    re.compile(r"^\d+[.)]\s*(?=\S)"),
    re.compile(r"^\d+\s+(?=\S)"),
    re.compile(r"^[ivxlcdm]+[.)]\s+", re.I),
    re.compile(r"^[a-z][.)]\s+", re.I),
]


def normalize_title(text: str) -> str:
    t = (text or "").strip()
    for pat in _PREFIXES:
        new = pat.sub("", t, count=1)
        if new != t:
            t = new
            break
    t = t.lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_GROUP_OF: Dict[str, int] = {}
for _gi, _grp in enumerate(_SYNONYM_GROUPS):
    for _term in _grp:
        _GROUP_OF[normalize_title(_term)] = _gi


def _tokens(norm: str) -> List[str]:
    return [w for w in norm.split() if w not in _STOP]


def match_score(required: str, heading: str) -> float:
    """0.0 (no match) .. 1.0 (identical). Matches count at >= MATCH_THRESHOLD."""
    r, h = normalize_title(required), normalize_title(heading)
    if not r or not h:
        return 0.0
    if r == h:
        return 1.0
    gr, gh = _GROUP_OF.get(r), _GROUP_OF.get(h)
    if gr is not None and gr == gh:
        return 0.95
    rt, ht = set(_tokens(r)), set(_tokens(h))
    if rt and ht:
        if rt <= ht and len(ht) <= len(rt) + 2:
            return 0.88
        if ht <= rt and len(rt) <= len(ht) + 2:
            return 0.84
    ratio = SequenceMatcher(None, r, h).ratio()
    return ratio if ratio >= MATCH_THRESHOLD else 0.0


# ---------------------------------------------------------------------------
# Template side
# ---------------------------------------------------------------------------

def normalize_required_sections(raw: Any) -> List[Dict[str, Any]]:
    """
    Flatten whatever shape required_sections has into
    [{"name", "level", "optional"}] in template order.
    Accepts: list of strings, list of dicts (name/title/heading/section,
    optional level, children/subsections/sections), JSON string, or
    newline-separated string.
    """
    if isinstance(raw, str):
        s = raw.strip()
        try:
            raw = json.loads(s)
        except (ValueError, TypeError):
            raw = [ln for ln in s.splitlines() if ln.strip()]
    if isinstance(raw, dict):
        raw = raw.get("sections") or raw.get("required_sections") or []

    out: List[Dict[str, Any]] = []

    def walk(items: Any, level: int) -> None:
        for it in items or []:
            if isinstance(it, str):
                name = it.strip()
                if name:
                    out.append({"name": name, "level": level, "optional": False})
            elif isinstance(it, dict):
                name = str(
                    it.get("name") or it.get("title") or it.get("heading")
                    or it.get("section") or ""
                ).strip()
                try:
                    lvl = int(
                        it.get("level") or it.get("heading_level")
                        or it.get("headingLevel") or level
                    )
                except (TypeError, ValueError):
                    lvl = level
                optional = bool(it.get("optional")) or it.get("required") is False
                if name:
                    out.append({"name": name, "level": lvl, "optional": optional})
                kids = (
                    it.get("children") or it.get("subsections")
                    or it.get("sections") or []
                )
                walk(kids, lvl + 1)

    walk(raw if isinstance(raw, list) else [], 1)
    return out


# ---------------------------------------------------------------------------
# Document side
# ---------------------------------------------------------------------------

_LEADER = re.compile(r"(\.{2,}|\t|\s{3,})\s*\d+\s*$")


def collect_candidate_headings(docx_path: str) -> List[Dict[str, Any]]:
    """Styled headings plus short, unstyled lines that look like headings."""
    from docx import Document

    doc = Document(docx_path)
    out: List[Dict[str, Any]] = []
    for idx, p in enumerate(doc.paragraphs):
        text = (p.text or "").strip()
        if not text or len(text) > 120:
            continue
        style = (p.style.name if p.style is not None else "") or ""
        sl = style.lower()
        # skip the entries inside a table of contents / list of figures
        if re.match(r"^toc\s*\d", sl) or "table of figures" in sl or sl.startswith("index"):
            continue

        styled = sl.startswith("heading") or sl == "title" or sl.startswith("toc heading")
        if styled:
            m = re.search(r"(\d+)", sl)
            level = int(m.group(1)) if m else 1
            out.append({"index": idx, "text": text, "level": level, "styled": True})
            continue

        # Unstyled: only accept short lines that look like headings.
        words = text.split()
        if len(words) > 10 or text.endswith((".", ",", ";", ":")):
            continue
        if _LEADER.search(text):
            continue
        numbered = bool(re.match(r"^(\d+(\.\d+)*[.)]?|chapter\s+\d+)\s*\S", text, re.I))
        shouty = text.isupper() and len(text) > 3
        runs = [r for r in p.runs if r.text.strip()]
        bold = bool(runs) and all(bool(r.bold) for r in runs)
        if numbered or shouty or bold:
            out.append({"index": idx, "text": text, "level": 1, "styled": False})
    return out


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_missing_sections(
    docx_path: str,
    required_sections: Any,
    max_level: Optional[int] = None,
) -> Dict[str, Any]:
    required = normalize_required_sections(required_sections)
    if max_level:
        required = [r for r in required if r["level"] <= int(max_level)]
    headings = collect_candidate_headings(docx_path)

    result: Dict[str, Any] = {
        "reliable": True,
        "reason": "",
        "required_count": len(required),
        "heading_count": len(headings),
        "found": [],
        "missing": [],
    }
    if not required:
        result["reliable"] = False
        result["reason"] = "Template has no required sections."
        return result
    if len(headings) < MIN_HEADINGS_FOR_RELIABLE:
        result["reliable"] = False
        result["reason"] = (
            "Too few headings detected in the document to judge missing sections. "
            "Apply heading styles first."
        )

    # best-score-first assignment; each heading and each required section used once
    pairs = []
    for ri, req in enumerate(required):
        for hi, h in enumerate(headings):
            s = match_score(req["name"], h["text"])
            if s >= MATCH_THRESHOLD:
                pairs.append((s + (0.01 if h["styled"] else 0.0), ri, hi, s))
    pairs.sort(key=lambda t: (-t[0], t[2]))

    assigned: Dict[int, int] = {}
    scores: Dict[int, float] = {}
    used_headings = set()
    for _, ri, hi, s in pairs:
        if ri in assigned or hi in used_headings:
            continue
        assigned[ri] = hi
        scores[ri] = s
        used_headings.add(hi)

    for ri, req in enumerate(required):
        if ri in assigned:
            h = headings[assigned[ri]]
            result["found"].append({
                "name": req["name"],
                "level": req["level"],
                "matched_heading": h["text"],
                "paragraph_index": h["index"],
                "score": round(scores[ri], 2),
            })
            continue
        # insert before the next (in template order) section that does exist
        insert_before = None
        for rj in range(ri + 1, len(required)):
            if rj in assigned:
                insert_before = headings[assigned[rj]]["index"]
                break
        result["missing"].append({
            "name": req["name"],
            "level": req["level"],
            "optional": req["optional"],
            "insert_before_paragraph_index": insert_before,
        })
    return result


def missing_sections_to_issues(missing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Issue dicts shaped like the other formatting issues the UI already shows."""
    issues = []
    for m in missing:
        name = m["name"]
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "section"
        msg = f'The required section "{name}" was not found in the document.'
        issues.append({
            "issue_id": f"missing_section_{slug}",
            "paragraph_id": "",
            "function": "formatting",
            "category": "Structure",
            "type": "missing_section",
            "code": "MISSING_SECTION",
            "severity": "minor" if m.get("optional") else "major",
            "reason": msg,
            "description": msg,
            "message": msg,
            "heading": name,
            "suggestion": f'Add a "{name}" section.',
            "fix_type": "insert_missing_section",
            "fix_details": {"section_name": name, "level": m.get("level", 1)},
            "source": "missing_section_detector",
        })
    return issues


# ---------------------------------------------------------------------------
# Fix: insert a placeholder section
# ---------------------------------------------------------------------------

def insert_missing_section_by_name(
    docx_path: str,
    required_sections: Any,
    section_name: str,
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Re-runs detection (paragraph indexes may have moved since the user saw the
    result), then inserts a heading + highlighted placeholder in template order.
    """
    from docx import Document
    from docx.enum.text import WD_COLOR_INDEX

    info = detect_missing_sections(docx_path, required_sections)
    target = next(
        (m for m in info["missing"]
         if m["name"].strip().lower() == section_name.strip().lower()),
        None,
    )
    if target is None:
        hit = next(
            (f for f in info["found"]
             if f["name"].strip().lower() == section_name.strip().lower()),
            None,
        )
        if hit:
            return {
                "inserted": False,
                "reason": (
                    f'The document already has a matching heading: "{hit["matched_heading"]}". '
                    "Restyle or rename that heading instead of adding a new section."
                ),
            }
        return {"inserted": False, "reason": "That section is not in the template's required sections."}
    if not info["reliable"]:
        return {"inserted": False, "reason": info["reason"]}

    doc = Document(docx_path)
    paras = doc.paragraphs
    name = target["name"]
    level = max(1, min(int(target.get("level") or 1), 4))
    placeholder = f"[Add your {name} content here]"

    # Optional AI/user supplied draft text (split on blank lines, capped).
    body_texts = [
        t.strip()
        for t in re.split(r"\n\s*\n", (content or "").strip()[:4000])
        if t.strip()
    ] or [placeholder]

    before = target["insert_before_paragraph_index"]
    if before is not None and 0 <= before < len(paras):
        anchor = paras[before]
        heading = anchor.insert_paragraph_before(name)
        bodies = [anchor.insert_paragraph_before(t) for t in body_texts]
    else:
        heading = doc.add_paragraph(name)
        bodies = [doc.add_paragraph(t) for t in body_texts]

    try:
        heading.style = doc.styles[f"Heading {level}"]
    except KeyError:
        for r in heading.runs:
            r.bold = True
    for body in bodies:  # highlighted so the student reviews it
        for r in body.runs:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW

    doc.save(docx_path)
    return {
        "inserted": True,
        "section_name": name,
        "level": level,
        "used_suggested_content": bool(content and content.strip()),
    }


# ---------------------------------------------------------------------------
# Preview data + AI draft helpers (used by the "ghost heading" in the preview)
# ---------------------------------------------------------------------------

def build_previews(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    One entry per missing section, shaped for the Word preview: where to draw
    the faded 'Missing' heading (insert_before_paragraph_id, or None = end of
    document) and what placeholder / suggested text to show in it.
    
    Handles edge cases:
    - Section at end of document (insert_before_paragraph_index = None)
    - Adjacent missing sections (they share the same insert_before, but appear in order)
    """
    out: List[Dict[str, Any]] = []
    missing = info.get("missing", [])
    
    # Track the last paragraph index we're inserting after, to handle adjacent missing sections
    last_insert_after_idx = None
    
    for i, m in enumerate(missing):
        name = m["name"]
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "section"
        before_idx = m.get("insert_before_paragraph_index")
        
        # Determine insert_after_paragraph_id:
        # - If this is the first missing section or before_idx changed from previous, 
        #   insert_after is the paragraph before before_idx
        # - If before_idx is None (end of doc), insert_after is the last existing paragraph
        # - For adjacent missing sections (same before_idx), they all insert after the same paragraph
        if before_idx is not None:
            # Insert before an existing paragraph
            if before_idx != last_insert_after_idx:
                # New insertion point - calculate insert_after
                insert_after_idx = before_idx - 1 if before_idx > 0 else None
                last_insert_after_idx = before_idx
            else:
                # Same insertion point as previous (adjacent missing sections)
                # Use the same insert_after_idx as calculated before
                insert_after_idx = out[-1].get("insert_after_paragraph_index")
                if isinstance(insert_after_idx, int):
                    insert_after_idx = insert_after_idx
        else:
            # End of document - insert after the last found section or last paragraph
            found = info.get("found", [])
            if found:
                insert_after_idx = found[-1].get("paragraph_index")
            else:
                insert_after_idx = None  # No existing sections at all
        
        insert_after_id = f"p{insert_after_idx}" if insert_after_idx is not None else None
        insert_before_id = f"p{before_idx}" if before_idx is not None else None
        
        # Build guidance text for specific section types if AI fails
        guidance = _section_guidance(name)
        
        out.append({
            "issue_id": f"missing_section_{slug}",
            "is_placeholder": True,
            "name": name,
            "level": m.get("level", 1),
            "optional": bool(m.get("optional")),
            "insert_before_paragraph_index": before_idx,
            "insert_before_paragraph_id": insert_before_id,
            "insert_after_paragraph_index": insert_after_idx,
            "insert_after_paragraph_id": insert_after_id,
            "position": "before" if before_idx is not None else "end",
            "placeholder_text": f"[Add your {name} content here]",
            "guidance_text": guidance,
            "suggested_content": None,
        })
    
    return out


def _section_guidance(section_name: str) -> str:
    """Return guidance text for common section types when AI generation fails."""
    name_lower = section_name.lower()
    
    guidance_map = {
        "abstract": "Summarize the problem, approach, key results and conclusion in 150-250 words.",
        "introduction": "Introduce the topic, state the problem, and outline the report structure.",
        "literature review": "Summarize relevant prior work and identify gaps this project addresses.",
        "methodology": "Describe the research methods, tools, and procedures used.",
        "results": "Present findings with clear data, tables, and figures.",
        "discussion": "Interpret results, explain significance, and compare with expectations.",
        "conclusion": "Summarize main findings, limitations, and suggest future work.",
        "references": "List all cited sources in the required citation format.",
        "acknowledgements": "Thank individuals or organizations who helped with the project.",
    }
    
    for key, guidance in guidance_map.items():
        if key in name_lower:
            return guidance
    
    return f"Write the content for the {section_name} section following your template guidelines."


def _get_document_hash(docx_path: str) -> str:
    """Hash the document text for cache invalidation."""
    from docx import Document
    doc = Document(docx_path)
    text = " ".join(p.text for p in doc.paragraphs if p.text.strip())
    return hashlib.md5(text.encode()).hexdigest()


async def generate_suggestion_with_cache(
    document_id: int,
    section_name: str,
    docx_path: str,
    client: Any,
    context: Dict[str, Any],
    timeout_seconds: float = 20.0,
) -> tuple[str | None, str | None]:
    """
    Generate AI suggestion for a missing section with caching.
    Returns (suggested_content, error_message).
    If AI fails or times out, returns (None, guidance_text).
    """
    import asyncio
    
    doc_hash = _get_document_hash(docx_path)
    cache_key = (document_id, section_name, doc_hash)
    
    # Check cache
    if cache_key in _SUGGESTION_CACHE:
        return _SUGGESTION_CACHE[cache_key], None
    
    # Generate with timeout
    try:
        async def _generate():
            prompt = build_suggestion_prompt(section_name, context)
            resp = await asyncio.wait_for(
                client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": prompt,
                    }],
                ),
                timeout=timeout_seconds,
            )
            content = "".join(
                getattr(b, "text", "") or ""
                for b in (getattr(resp, "content", None) or [])
            ).strip()
            return content
        
        suggested = await _generate()
        if suggested:
            _SUGGESTION_CACHE[cache_key] = suggested
            return suggested, None
    except asyncio.TimeoutError:
        guidance = _section_guidance(section_name)
        return None, f"AI generation timed out. {guidance}"
    except Exception as exc:
        guidance = _section_guidance(section_name)
        return None, f"AI generation failed: {str(exc)[:100]}. {guidance}"
    
    # Fallback to guidance
    guidance = _section_guidance(section_name)
    return None, guidance


def document_context(docx_path: str, max_chars: int = 1500) -> Dict[str, Any]:
    """Headings + a short excerpt of body text, used to ground an AI draft."""
    from docx import Document

    heads = [h["text"] for h in collect_candidate_headings(docx_path)][:60]
    head_set = set(heads)
    parts: List[str] = []
    total = 0
    for p in Document(docx_path).paragraphs:
        t = (p.text or "").strip()
        if len(t) < 60 or t in head_set:
            continue
        parts.append(t)
        total += len(t)
        if total >= max_chars:
            break
    return {"headings": heads, "excerpt": " ".join(parts)[:max_chars]}


def build_suggestion_prompt(section_name: str, context: Dict[str, Any]) -> str:
    heads = "\n- ".join(context.get("headings") or [])
    return (
        "A student is writing a university final year project report that is "
        f'missing its "{section_name}" section.\n\n'
        f"Existing headings:\n- {heads}\n\n"
        f"Excerpt from the report:\n{context.get('excerpt', '')}\n\n"
        f'Write a short starting draft (1-2 short paragraphs) for the "{section_name}" '
        "section that fits this report. Rules: do not invent results, numbers, names "
        "or citations; put [square brackets] where the student must add specifics; "
        "plain text only, no headings, no bullet symbols, no preamble."
    )
