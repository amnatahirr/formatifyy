"""
routers/structure_style_toc_router.py
═══════════════════════════════════════════════════════════════════════════════
Endpoints that power the Structure tab, Paragraph Style tab, and TOC tab
on the Analyze screen.

Register in main.py:
    from routers.structure_style_toc_router import router as sst_router
    app.include_router(sst_router)

All endpoints are prefixed with /api (via the APIRouter prefix).

Endpoints:
  POST /api/heading-style-check/{document_id}   → check all required headings
  POST /api/paragraph-style-check/{document_id} → check all body paragraphs
  GET  /api/toc-check/{document_id}             → detect + cross-check TOC
  POST /api/apply-heading-style/{document_id}   → fix one heading's style
  POST /api/add-missing-heading/{document_id}   → insert missing heading
  POST /api/apply-paragraph-style/{document_id} → bulk fix paragraph styles
  POST /api/apply-toc-style/{document_id}       → apply Word TOC styles to existing TOC
  POST /api/add-toc/{document_id}               → insert a new TOC block (NEW)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import re
import json
import shutil
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import get_db
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree
from services.heading_normalizer import detect_headings_from_template
from services.heading_detector_v2 import detect_headings_v2, detect_headings_v2_from_doc, _find_title_page_end
from formatter.docx_formatter import apply_template_headings

router = APIRouter(prefix="/api", tags=["Structure Style & TOC"])

WORKING_FOLDER = "uploads/working"
os.makedirs(WORKING_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _working_copy_path(document_id: int) -> str:
    return os.path.join(WORKING_FOLDER, f"doc_{document_id}_working.docx")


def _get_effective_path(document_id: int, original_path: str) -> str:
    wc = _working_copy_path(document_id)
    return wc if os.path.exists(wc) else original_path


def _get_doc_and_template(document_id: int, user_id: int) -> Tuple[dict, dict, str]:
    """Returns (doc_row, template_row, effective_file_path)."""
    conn = get_db()
    doc = conn.execute(
        "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["user_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Unauthorized")

    template = conn.execute(
        "SELECT * FROM templates WHERE id = ?", (doc["template_id"],)
    ).fetchone()
    conn.close()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found for this document")

    file_path = _get_effective_path(document_id, doc["file_path"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    return dict(doc), dict(template), file_path


def _parse_formatting_rules(template: dict) -> dict:
    raw = template.get("formatting_rules", "{}")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw or {}


def _parse_required_sections(template: dict) -> List[dict]:
    raw = template.get("required_sections", "[]")
    if isinstance(raw, str):
        try:
            sections = json.loads(raw)
        except Exception:
            return []
    else:
        sections = raw or []

    result = []
    for i, item in enumerate(sections):
        if isinstance(item, str):
            result.append({"name": item, "order": i + 1, "required": True})
        else:
            result.append({
                "name": item.get("name", ""),
                "aliases": item.get("aliases", []),
                "order": item.get("order", i + 1),
                "required": item.get("required", True),
            })
    return result


def _heading_style_for_level(rules: dict, level: int) -> dict:
    """Returns expected style dict for a heading level from template rules."""
    defaults = {
        1: {"font_name": "Times New Roman", "font_size": 16, "bold": True,  "alignment": "left"},
        2: {"font_name": "Times New Roman", "font_size": 14, "bold": True,  "alignment": "left"},
        3: {"font_name": "Times New Roman", "font_size": 13, "bold": True,  "alignment": "left"},
        4: {"font_name": "Times New Roman", "font_size": 12, "bold": False, "alignment": "left"},
    }
    base = defaults.get(level, defaults[2]).copy()

    for key_variant in (f"heading{level}", f"h{level}", f"Heading{level}"):
        if key_variant in rules:
            base.update(rules[key_variant])
            break

    if "headings" in rules:
        base.update(rules["headings"])

    return base


def _paragraph_style(rules: dict) -> dict:
    """Returns expected paragraph style from template rules."""
    base = {
        "font_name": "Times New Roman",
        "font_size": 11,
        "bold": False,
        "line_spacing": 1.0,
        "alignment": "justify",
        "space_before": 0,
        "space_after": 6,
    }
    for key in ("paragraph", "body", "normal"):
        if key in rules:
            base.update(rules[key])
            break
    # Also support flat keys like body_font, body_size
    if "body_font" in rules:
        base["font_name"] = rules["body_font"]
    if "body_size" in rules:
        base["font_size"] = rules["body_size"]
    if "body_line_spacing" in rules:
        base["line_spacing"] = rules["body_line_spacing"]
    return base


def _get_para_font_info(para) -> dict:
    """Extract actual font name, size, bold from a paragraph's runs."""
    font_names, font_sizes, bolds = [], [], []
    for run in para.runs:
        if run.font.name:
            font_names.append(run.font.name)
        if run.font.size:
            font_sizes.append(run.font.size.pt)
        if run.font.bold is not None:
            bolds.append(run.font.bold)
    return {
        "font_name": font_names[0] if font_names else None,
        "font_size": font_sizes[0] if font_sizes else None,
        "bold": bolds[0] if bolds else None,
    }


def _get_para_spacing(para) -> dict:
    """Extract line spacing and alignment from paragraph format."""
    pf = para.paragraph_format
    line_spacing = None
    if pf.line_spacing is not None:
        try:
            ls = pf.line_spacing
            if hasattr(ls, "pt"):
                line_spacing = round(ls.pt / 12.0, 2)
            else:
                line_spacing = round(float(ls), 2)
        except Exception:
            pass

    alignment_map = {
        WD_ALIGN_PARAGRAPH.LEFT:    "left",
        WD_ALIGN_PARAGRAPH.CENTER:  "center",
        WD_ALIGN_PARAGRAPH.RIGHT:   "right",
        WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
    }
    return {
        "line_spacing": line_spacing,
        "alignment": alignment_map.get(pf.alignment, "left"),
        "space_before": int(pf.space_before.pt) if pf.space_before else 0,
        "space_after":  int(pf.space_after.pt)  if pf.space_after  else 0,
    }


def _apply_style_to_para(para, style_spec: dict):
    """Mutate a paragraph's runs to match style_spec."""
    if not para.runs:
        # paragraph has no runs (e.g. it only has text at para level) — add one
        run = para.add_run(para.text)
        # Clear the paragraph text node so we don't duplicate
        for child in list(para._element):
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "r":
                continue
            if tag == "t":
                child.getparent().remove(child)

    for run in para.runs:
        if style_spec.get("font_name"):
            run.font.name = style_spec["font_name"]
        if style_spec.get("font_size"):
            run.font.size = Pt(style_spec["font_size"])
        if "bold" in style_spec:
            run.font.bold = style_spec["bold"]

    pf = para.paragraph_format
    if style_spec.get("line_spacing") is not None:
        pf.line_spacing = style_spec["line_spacing"]
    if style_spec.get("space_before") is not None:
        pf.space_before = Pt(style_spec["space_before"])
    if style_spec.get("space_after") is not None:
        pf.space_after = Pt(style_spec["space_after"])

    align_map = {
        "left":    WD_ALIGN_PARAGRAPH.LEFT,
        "center":  WD_ALIGN_PARAGRAPH.CENTER,
        "right":   WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    if style_spec.get("alignment") in align_map:
        pf.alignment = align_map[style_spec["alignment"]]


def _detect_heading_level_from_style(para_style_name: str) -> Optional[int]:
    low = (para_style_name or "").lower()
    for lvl in (1, 2, 3, 4):
        if f"heading {lvl}" in low or f"heading{lvl}" in low:
            return lvl
    return None


def _detect_heading_level(para) -> Optional[int]:
    """
    Detect heading level from a paragraph using BOTH style name AND font size.

    KEY FIX: COMSATS FYP documents use 'Normal' style throughout but signal
    headings via font size (18pt = H1, 14pt = H2).  Checking only the Word
    style name misses all of these headings and falsely reports them as missing.

    Priority:
      1. Explicit Word Heading style  (most reliable)
      2. Font size >= 18pt            → H1
      3. Font size >= 14pt            → H2
      4. ALL CAPS short text          → H2
      5. Bold + short + no period     → H3
    """
    # 1. Explicit style
    lvl = _detect_heading_level_from_style(para.style.name)
    if lvl is not None:
        return lvl

    text = para.text.strip()
    if not text:
        return None

    word_count = len(text.split())
    ends_sentence = text.endswith((".", "?", "!"))

    # Collect font size from runs
    font_size = None
    for run in para.runs:
        if run.font.size:
            font_size = run.font.size.pt
            break

    # 2. Font size >= 18pt → H1
    if font_size and font_size >= 18 and word_count <= 12 and not ends_sentence:
        return 1

    # 3. Font size >= 14pt → H2
    if font_size and font_size >= 14 and word_count <= 12 and not ends_sentence:
        return 2

    # 4. ALL CAPS short line
    if text.isupper() and 1 <= word_count <= 8:
        return 2

    # 5. Bold + short + no sentence punctuation
    is_bold = any(r.bold for r in para.runs if r.text.strip())
    if is_bold and word_count <= 10 and not ends_sentence:
        return 3

    return None


def _fuzzy_match(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())
    return norm(a) == norm(b) or norm(a) in norm(b) or norm(b) in norm(a)


def _norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _is_cover_page_suppress(text: str) -> bool:
    """
    Returns True if the text should NOT become a TOC heading entry.
    Covers cover-page metadata, long body text, and 'Label: sentence' bullets.
    """
    t = text.strip()
    if not t:
        return True

    lower = t.lower()

    # Guard 2 ─ length: real headings are never 200+ chars
    if len(t) > 200:
        return True

    # Guard 5 ─ 'Label: explanation sentence' body bullets
    if ':' in t:
        after_colon = t.split(':', 1)[1].strip()
        if len(after_colon.split()) > 8:
            return True

    # Guard 3 ─ explicit cover-page text patterns
    COVER_PATTERNS = [
        "submitted in partial",
        "fulfilment of",
        "session 20",            # e.g. "Session 2023-2027"
        "4th year",
        "final year project proposal",
        "department of",
        "university islamabad",
        "university degree",
        "reg no",
        "roll no",
        "submitted by",
        "supervisor",
        "co-supervisor",
        "registration",
        "student name",
    ]
    if any(p in lower for p in COVER_PATTERNS):
        return True

    # Underscore signature / blank line pattern
    if "____" in t:
        return True

    # 1. Date patterns (e.g. "April 2024", "20-04-2024", "2024")
    if re.search(r'\b(19|20)\d{2}\b', t) and len(t.split()) <= 4:
        return True

    # 2. Student ID pattern like SP21-BSE-001
    if re.search(r'[A-Z]{2}\d{2}-[A-Z]{3}-\d{3}', t):
        return True

    # 3. Institution patterns
    if any(p in lower for p in ["university", "department", "faculty",
                                 "campus", "institute", "college"]):
        return True

    # 4. Short fragments (under 4 words) that aren’t known headings
    real_headings = {
        "abstract", "introduction", "preface", "acknowledgement",
        "acknowledgments", "dedication", "conclusion", "references", "bibliography"
    }
    if len(t.split()) < 4:
        norm = re.sub(r'[^a-z]', '', lower)
        if norm not in real_headings:
            return True

    return False


def _find_cover_page_end_index(doc) -> int:
    """
    Returns the paragraph index at which the cover page ends (exclusive).
    Paragraphs with index < returned value are treated as cover-page content.

    Priority:
      1. Hard page break — the paragraph that contains the first page break.
      2. Text-based scan — the first paragraph whose normalised text is
         'abstract' or 'introduction'.
    """
    from docx.oxml.ns import qn as _qn
    for i, para in enumerate(doc.paragraphs):
        for br in para._element.iter(_qn("w:br")):
            if br.get(_qn("w:type")) == "page":
                return i  # everything up to and including this para is cover page
    # Text-based fallback
    for i, para in enumerate(doc.paragraphs):
        t = re.sub(r'[^a-z]', '', para.text.strip().lower())
        if t in ('abstract', 'introduction'):
            return i  # everything BEFORE the abstract is cover page
    return 0



def _is_toc_paragraph(para) -> bool:
    style_name = (para.style.name or "").lower()
    if "toc" in style_name or "table of contents" in style_name:
        return True
    text = para.text.strip()
    if re.match(r"^.{3,60}[.\s]{3,}\d{1,4}\s*$", text):
        return True
    return False


def _get_toc_para_indices(doc) -> set:
    """
    Returns set of paragraph indices that are TOC field result paragraphs.
    These sit between a fldChar 'separate' and fldChar 'end' for a TOC field.
    Catches TOC 1/TOC 2 styled lines that _is_toc_paragraph misses.
    """
    from docx.oxml.ns import qn
    toc_indices = set()
    in_toc_field = False
    seen_toc_instr = False

    for i, para in enumerate(doc.paragraphs):
        for elem in para._element.iter():
            local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if local == 'instrText' and 'TOC' in (elem.text or ''):
                seen_toc_instr = True
            if local == 'fldChar':
                ftype = elem.get(qn('w:fldCharType'), '')
                if ftype == 'separate' and seen_toc_instr:
                    in_toc_field = True
                elif ftype == 'end' and in_toc_field:
                    in_toc_field = False
                    seen_toc_instr = False
        if in_toc_field:
            toc_indices.add(i)

    return toc_indices


def _make_working_copy(document_id: int, original_path: str) -> str:
    """Ensures a working copy exists and returns its path."""
    wc = _working_copy_path(document_id)
    if not os.path.exists(wc):
        shutil.copy2(original_path, wc)
    return wc


def _ensure_docx(file_path: str, endpoint: str):
    if not file_path.lower().endswith(".docx"):
        raise HTTPException(
            status_code=400,
            detail=f"{endpoint} only supports .docx files. Upload a Word document."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Heading Style Check
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/heading-style-check/{document_id}")
def heading_style_check(
    document_id: int,
    user_id: int = Query(...),
) -> JSONResponse:
    """
    Two-layer Heading Style Check.
    Uses Style Match (Layer 1) and Text Match (Layer 2).
    """
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    sections = _parse_required_sections(template)

    if not file_path.lower().endswith(".docx"):
        return JSONResponse(content={
            "document_id": document_id,
            "error": "Style check only supported for .docx files.",
            "results": []
        })

    wc_path = _working_copy_path(document_id)
    check_path = wc_path if os.path.exists(wc_path) else file_path

    results = detect_headings_v2(check_path, sections)

    # Transform to flat list that Flutter expects (Fixes Bug 1 & 2)
    flat_results = []

    for key, h in results.get("foundHeadings", {}).items():
        # h is a dict: {"templateHeading": "...", "paraIndex": int, "matchType": "..."}
        name = h.get("templateHeading") or key  # fallback to dict key
        if not name:
            continue
        flat_results.append({
            "heading":      name,           # ← this is what Flutter displays
            "status":       "found",
            "matchType":    h.get("matchType", "exact"),
            "paraIndex":    h.get("paraIndex"),
            "styleCorrect": True,
        })

    for key, h in results.get("missingStyleHeadings", {}).items():
        name = h.get("templateHeading") or key
        if not name:
            continue
        para_idx = h.get("paraIndex")
        if para_idx is None:
            continue  # no paragraph to style — skip entirely
        flat_results.append({
            "heading":      name,
            "status":       "missing_style",
            "matchType":    h.get("matchType", "contains"),
            "paraIndex":    int(para_idx),  # ← must be int, never null
            "currentStyle": h.get("currentStyle", "Normal"),
            "styleCorrect": False,
        })

    return JSONResponse(content={
        "document_id":   document_id,
        "template_name": template["name"],
        "results":       flat_results,       # only entries with valid int paraIndex
        "trulyMissing":  [                   # informational only, no Apply button
            h.get("templateHeading", h) if isinstance(h, dict) else h
            for h in results.get("truelyMissing", [])
        ],
        "wronglyStyled": results.get("wronglyStyledParagraphs", []),
        "checked_path":  os.path.basename(check_path)
    })


@router.post("/apply-all-heading-fixes/{document_id}")
def apply_all_heading_fixes(
    document_id: int,
    user_id: int = Query(...),
) -> JSONResponse:
    """
    Bulk fix for all heading style issues.
    Uses a single Document object to avoid paragraph-index drift.
    """
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    _ensure_docx(file_path, "apply-all-heading-fixes")

    rules = _parse_formatting_rules(template)
    sections = _parse_required_sections(template)
    h1_style = _heading_style_for_level(rules, 1)

    wc = _make_working_copy(document_id, file_path)
    docx = Document(wc)

    # Compute cover-page boundary once
    cover_page_end = _find_cover_page_end_index(docx)
    print(f"[HeadingFix] cover_page_end={cover_page_end}")

    # Detect current state using in-memory doc to ensure index alignment
    results = detect_headings_v2_from_doc(docx, sections)

    # 1. Apply styles to missingStyleHeadings (with guards)
    fixed_count = 0
    missing_indices = {item["paraIndex"] for item in results["missingStyleHeadings"].values()}

    for item in results["missingStyleHeadings"].values():
        para_idx = item["paraIndex"]
        if not (0 <= para_idx < len(docx.paragraphs)):
            continue
        para = docx.paragraphs[para_idx]
        para_text = para.text.strip()

        # Guard 1 ─ cover-page boundary
        if para_idx < cover_page_end:
            print(f"[HeadingFix] SKIP para {para_idx} (cover page): {para_text[:60]!r}")
            continue
        # Guard 2 ─ length
        if len(para_text) > 200:
            print(f"[HeadingFix] SKIP para {para_idx} (too long, {len(para_text)} chars)")
            continue
        # Guard 3 ─ cover-page text patterns
        if _is_cover_page_suppress(para_text):
            print(f"[HeadingFix] SKIP para {para_idx} (cover pattern): {para_text[:60]!r}")
            continue

        try:
            para.style = docx.styles["Heading 1"]
        except Exception:
            pass
        _apply_style_to_para(para, h1_style)
        fixed_count += 1

    # 2. Revert wronglyStyledParagraphs to Normal
    #    Includes: detector-flagged, cover-page paragraphs, long body paragraphs
    wrong_indices = {item["paraIndex"] for item in results["wronglyStyledParagraphs"]}
    safe_to_revert = wrong_indices - missing_indices

    reverted_count = 0
    for item in results["wronglyStyledParagraphs"]:
        para_idx = item["paraIndex"]
        if para_idx in safe_to_revert and 0 <= para_idx < len(docx.paragraphs):
            para = docx.paragraphs[para_idx]
            try:
                para.style = docx.styles["Normal"]
            except Exception:
                pass
            for run in para.runs:
                run.bold = None
                run.font.size = None
            reverted_count += 1

    # 3. Extra sweep: revert cover-page and long paragraphs that still carry
    #    a Heading style but were missed by the detector (e.g. para 3, 7, 27)
    for i, para in enumerate(docx.paragraphs):
        sn = para.style.name if para.style else ""
        if not sn.startswith("Heading"):
            continue
        para_text = para.text.strip()
        should_revert = False
        reason = ""
        if i < cover_page_end:
            should_revert, reason = True, "cover-page index"
        elif len(para_text) > 200:
            should_revert, reason = True, "text too long"
        elif _is_cover_page_suppress(para_text):
            should_revert, reason = True, "cover-page pattern"
        if should_revert and i not in missing_indices:
            print(f"[HeadingFix] REVERT para {i} ({reason}): {para_text[:60]!r}")
            try:
                para.style = docx.styles["Normal"]
            except Exception:
                pass
            for run in para.runs:
                run.bold = None
                run.font.size = None
            reverted_count += 1

    docx.save(wc)

    # Refresh results for UI
    final_results = detect_headings_v2(wc, sections)

    flat_results = []
    for key, h in final_results.get("foundHeadings", {}).items():
        name = h.get("templateHeading") or key
        flat_results.append({
            "heading":      name,
            "status":       "found",
            "matchType":    h.get("matchType", "exact"),
            "paraIndex":    h.get("paraIndex"),
            "styleCorrect": True,
        })

    for key, h in final_results.get("missingStyleHeadings", {}).items():
        name = h.get("templateHeading") or key
        para_idx = h.get("paraIndex")
        if para_idx is not None:
            flat_results.append({
                "heading":      name,
                "status":       "missing_style",
                "matchType":    h.get("matchType", "contains"),
                "paraIndex":    int(para_idx),
                "currentStyle": h.get("currentStyle", "Normal"),
                "styleCorrect": False,
            })

    return JSONResponse(content={
        "status": "ok",
        "message": f"Applied fixes to {fixed_count} headings and reverted {reverted_count} paragraphs.",
        "results": flat_results,
        "trulyMissing": [
            h.get("templateHeading", h) if isinstance(h, dict) else h
            for h in final_results.get("truelyMissing", [])
        ],
        "wronglyStyled": final_results["wronglyStyledParagraphs"]
    })




# ─────────────────────────────────────────────────────────────────────────────
# 2. Paragraph Style Check
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/paragraph-style-check/{document_id}")
def paragraph_style_check(
    document_id: int,
    user_id: int = Query(...),
) -> JSONResponse:
    """
    Scans all body paragraphs (non-heading, non-empty, non-TOC) and returns
    those whose font / size / alignment / line-spacing doesn't match the
    template's paragraph spec.
    """
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    rules    = _parse_formatting_rules(template)
    expected = _paragraph_style(rules)

    if not file_path.lower().endswith(".docx"):
        return JSONResponse(content={
            "document_id":    document_id,
            "expected_style": expected,
            "issues": [],
            "summary": {"total_checked": 0, "issues": 0, "ok": 0},
            "note": "Paragraph style check only supported for .docx files.",
        })
    # ── Prefer the working copy so applied fixes are visible immediately ────
    wc_path = _working_copy_path(document_id)
    check_path = wc_path if os.path.exists(wc_path) else file_path

    docx = Document(check_path)
    issues: List[dict] = []
    total_checked = 0

    toc_indices    = _get_toc_para_indices(docx)
    title_page_end = _find_title_page_end(docx)
    print(f"[StyleCheck] title_page_end={title_page_end}, toc_indices count={len(toc_indices)}")

    for i, para in enumerate(docx.paragraphs):
        if i <= title_page_end:
            continue   # skip cover page / front matter
        if i in toc_indices:
            continue   # skip TOC field result paragraphs
        text = para.text.strip()
        if not text:
            continue
        style_name = (para.style.name or "").lower()
        if "heading" in style_name or "title" in style_name:
            continue
        if _is_toc_paragraph(para):
            continue

        total_checked += 1
        actual_font    = _get_para_font_info(para)
        actual_spacing = _get_para_spacing(para)
        mismatches: List[dict] = []

        if expected.get("font_name") and actual_font.get("font_name") and \
           actual_font["font_name"].lower() != expected["font_name"].lower():
            mismatches.append({
                "property": "font_name",
                "expected": expected["font_name"],
                "actual":   actual_font["font_name"],
            })
        if expected.get("font_size") and actual_font.get("font_size") and \
           abs(actual_font["font_size"] - expected["font_size"]) > 0.5:
            mismatches.append({
                "property": "font_size",
                "expected": expected["font_size"],
                "actual":   round(actual_font["font_size"], 1),
            })
        if expected.get("alignment") and actual_spacing.get("alignment") and \
           actual_spacing["alignment"] != expected["alignment"]:
            mismatches.append({
                "property": "alignment",
                "expected": expected["alignment"],
                "actual":   actual_spacing["alignment"],
            })
        if expected.get("line_spacing") and actual_spacing.get("line_spacing") and \
           abs((actual_spacing["line_spacing"] or 0) - expected["line_spacing"]) > 0.15:
            mismatches.append({
                "property": "line_spacing",
                "expected": expected["line_spacing"],
                "actual":   actual_spacing["line_spacing"],
            })

        if mismatches:
            issues.append({
                "para_index":   i,
                "text_preview": (text[:80] + "…") if len(text) > 80 else text,
                "mismatches":   mismatches,
                "expected_style": expected,
                "actual_style":   {**actual_font, **actual_spacing},
            })

    return JSONResponse(content={
        "document_id":    document_id,
        "expected_style": expected,
        "issues":         issues,
        "summary": {
            "total_checked": total_checked,
            "issues":        len(issues),
            "ok":            total_checked - len(issues),
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# 3. TOC Check
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/toc-check/{document_id}")
def toc_check(
    document_id: int,
    user_id: int = Query(...),
) -> JSONResponse:
    """
    Detects TOC entries and cross-checks them against document headings.
    """
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)

    if not file_path.lower().endswith(".docx"):
        return JSONResponse(content={
            "document_id":       document_id,
            "has_toc":           False,
            "status":            "not_docx",
            "message":           "TOC check only supported for .docx files.",
            "toc_entries":       [],
            "document_headings": [],
            "missing_from_toc":  [],
            "extra_in_toc":      [],
            "summary":           {},
        })

    # ── Prefer the working copy so corrections are visible ──────────────────
    wc_path = _working_copy_path(document_id)
    check_path = wc_path if os.path.exists(wc_path) else file_path

    docx = Document(check_path)
    toc_entries: List[dict] = []
    doc_headings_list: List[dict] = []
    has_toc = False

    seen_first_real_heading = False
    for para in docx.paragraphs:
        style_name = (para.style.name or "").lower()
        text = para.text.strip()
        if not text:
            continue

        if _is_toc_paragraph(para):
            has_toc = True
            match = re.match(r"^(.+?)[.\s]{2,}(\d{1,4})\s*$", text)
            if match:
                toc_entries.append({
                    "text":  match.group(1).strip(),
                    "page":  int(match.group(2)),
                    "style": style_name,
                })
            else:
                toc_entries.append({"text": text, "page": None, "style": style_name})

        lvl = _detect_heading_level(para)
        if lvl is not None:
            # Suppression logic for cover page
            if not seen_first_real_heading:
                norm_h = _norm_text(text)
                if norm_h in ("abstract", "introduction"):
                    seen_first_real_heading = True
                elif _is_cover_page_suppress(text):
                    continue

            doc_headings_list.append({
                "text":  text,
                "level": lvl,
                "style": para.style.name,
            })

    print(f"[TOC] Found {len(doc_headings_list)} headings in {os.path.basename(check_path)} for comparison")

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

    toc_texts = {norm(e["text"]) for e in toc_entries}
    doc_texts  = {norm(h["text"]) for h in doc_headings_list}

    missing_from_toc = [h for h in doc_headings_list if norm(h["text"]) not in toc_texts]
    extra_in_toc     = [e for e in toc_entries       if norm(e["text"]) not in doc_texts]

    if not has_toc:
        status = "missing_toc"
    elif not toc_entries:
        status = "empty_toc"
    elif missing_from_toc:
        status = "incomplete_toc"
    else:
        status = "ok"

    return JSONResponse(content={
        "document_id":       document_id,
        "has_toc":           has_toc,
        "status":            status,
        "toc_entries":       toc_entries,
        "document_headings": doc_headings_list,
        "missing_from_toc":  missing_from_toc,
        "extra_in_toc":      extra_in_toc,
        "summary": {
            "toc_entry_count":  len(toc_entries),
            "heading_count":    len(doc_headings_list),
            "missing_from_toc": len(missing_from_toc),
            "extra_in_toc":     len(extra_in_toc),
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. Apply Heading Style
# ─────────────────────────────────────────────────────────────────────────────

class ApplyHeadingStyleRequest(BaseModel):
    para_index:    int
    heading_level: int = 1


@router.post("/apply-heading-style/{document_id}")
def apply_heading_style(
    document_id: int,
    user_id: int = Query(...),
    body: ApplyHeadingStyleRequest = Body(...),
) -> JSONResponse:
    """Apply the template's heading style to the paragraph at para_index."""
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    _ensure_docx(file_path, "apply-heading-style")

    rules      = _parse_formatting_rules(template)
    style_spec = _heading_style_for_level(rules, body.heading_level)

    wc   = _make_working_copy(document_id, file_path)
    docx = Document(wc)

    if body.para_index >= len(docx.paragraphs):
        raise HTTPException(status_code=400, detail="para_index out of range")

    para = docx.paragraphs[body.para_index]
    _apply_style_to_para(para, style_spec)

    # Set Word built-in heading style so the TOC picks it up
    try:
        para.style = docx.styles[f"Heading {body.heading_level}"]
    except Exception:
        pass  # Style might not exist in this doc; font override is sufficient

    docx.save(wc)

    return JSONResponse(content={
        "status":  "ok",
        "message": f"Heading style H{body.heading_level} applied at paragraph {body.para_index}.",
        "applied": style_spec,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 5. Add Missing Heading
# ─────────────────────────────────────────────────────────────────────────────

class AddMissingHeadingRequest(BaseModel):
    section_name:  str
    heading_level: int = 1
    # insert_before_index: if given → insert before that paragraph index
    insert_before_index: Optional[int] = None
    # insert_at_end: Flutter sends True for missing headings
    insert_at_end: bool = False
    # section_order: 1-based position of this section in the template.
    # When provided the heading is placed in the correct sequential position
    # rather than being blindly appended after all existing content.
    section_order: Optional[int] = None


@router.post("/add-missing-heading/{document_id}")
def add_missing_heading(
    document_id: int,
    user_id: int = Query(...),
    body: AddMissingHeadingRequest = Body(...),
) -> JSONResponse:
    """
    Insert a missing heading (with template styling) at the correct position.

    Logic (priority order):
    1. insert_before_index is given  → insert before that paragraph index.
    2. section_order is given        → find the first subsequent template section
                                       that already exists in the document and
                                       insert BEFORE it (correct ordering).
    3. Fallback                      → append before the final sectPr.
    """
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    _ensure_docx(file_path, "add-missing-heading")

    rules      = _parse_formatting_rules(template)
    style_spec = _heading_style_for_level(rules, body.heading_level)

    wc   = _make_working_copy(document_id, file_path)
    docx = Document(wc)

    body_elem  = docx.element.body
    paragraphs = docx.paragraphs

    # ── NEW: Check if this section already exists but is just unstyled ──────
    # We use the new detect_headings_v2 to find existing headings that are unstyled.
    sections = _parse_required_sections(template)
    results = detect_headings_v2(wc, sections)
    
    this_norm = _norm_text(body.section_name)
    # Check if this section is in missingStyleHeadings
    match = next(
        (m for m in results["missingStyleHeadings"] if _norm_text(m["templateHeading"]) == this_norm),
        None
    )

    if match:
        para_idx = match["paraIndex"]
        if para_idx < len(docx.paragraphs):
            para = docx.paragraphs[para_idx]
            # Set Word style
            try:
                para.style = docx.styles[f"Heading {body.heading_level}"]
            except:
                pass
            # Apply template styling
            _apply_style_to_para(para, style_spec)
            
            docx.save(wc)
            print(f"[HeadingApply] Applied heading style to existing paragraph at index {para_idx}")
            
            return JSONResponse(content={
                "status":  "ok",
                "message": f"Existing heading '{body.section_name}' found at index {para_idx} and restyled.",
                "applied": style_spec,
            })


    if body.insert_before_index is not None:
        # Caller explicitly specified the insertion index
        idx = min(body.insert_before_index, len(paragraphs))
        ref_elem = paragraphs[idx]._element if idx < len(paragraphs) else None

    elif body.section_order is not None:
        # ── KEY FIX: insert in the correct sequential order ──────────────────
        # Load the full ordered section list from the template
        conn2 = get_db()
        tmpl2 = conn2.execute(
            "SELECT required_sections FROM templates WHERE id = ?",
            (doc_row["template_id"],),
        ).fetchone()
        conn2.close()

        ordered_names: list = []
        if tmpl2:
            try:
                raw = json.loads(tmpl2["required_sections"])
                ordered_names = [
                    (item["name"] if isinstance(item, dict) else str(item))
                    for item in raw
                ]
            except Exception:
                pass

        # Build a map: normalised_heading_text → paragraph element
        def _norm(s: str) -> str:
            return re.sub(r"[^a-z0-9]", "", s.lower())

        heading_elem_map: dict = {}
        for para in paragraphs:
            if _detect_heading_level(para) is not None and para.text.strip():
                heading_elem_map[_norm(para.text.strip())] = para._element

        # Find the index of this section in the template order
        this_norm = _norm(body.section_name)
        try:
            insert_idx = next(
                i for i, n in enumerate(ordered_names)
                if _norm(n) == this_norm
            )
        except StopIteration:
            insert_idx = len(ordered_names)

        # Walk the template sections that come AFTER this one.
        # The first one that already exists in the document is our anchor.
        ref_elem = None
        for subsequent_name in ordered_names[insert_idx + 1:]:
            key = _norm(subsequent_name)
            if key in heading_elem_map:
                ref_elem = heading_elem_map[key]
                break
        # ref_elem is None → will fall through to append at end (correct)

    else:
        # Legacy fallback: append at end of document body
        ref_elem = None

    # ── Build new heading paragraph element ──────────────────────────────────
    new_para_elem = OxmlElement("w:p")

    if ref_elem is not None:
        body_elem.insert(list(body_elem).index(ref_elem), new_para_elem)
    else:
        # Insert before the final sectPr so the section properties stay last
        sect_pr = body_elem.find(qn("w:sectPr"))
        if sect_pr is not None:
            body_elem.insert(list(body_elem).index(sect_pr), new_para_elem)
        else:
            body_elem.append(new_para_elem)

    # ── Set text, font, and Word heading style ────────────────────────────────
    from docx.text.paragraph import Paragraph as DocxParagraph
    new_para = DocxParagraph(new_para_elem, docx)
    new_para.text = body.section_name
    _apply_style_to_para(new_para, style_spec)
    try:
        new_para.style = docx.styles[f"Heading {body.heading_level}"]
    except Exception:
        pass

    # ── Add a placeholder body paragraph immediately after the heading ────────
    placeholder_elem = OxmlElement("w:p")
    idx_new = list(body_elem).index(new_para_elem)
    body_elem.insert(idx_new + 1, placeholder_elem)

    from docx.text.paragraph import Paragraph as DocxParagraph2
    placeholder = DocxParagraph2(placeholder_elem, docx)
    placeholder.text = f"[Add content for {body.section_name} here]"
    para_style = _paragraph_style(rules)
    _apply_style_to_para(placeholder, para_style)

    docx.save(wc)

    return JSONResponse(content={
        "status":  "ok",
        "message": f'Heading "{body.section_name}" (H{body.heading_level}) inserted with template style.',
        "applied": style_spec,
    })


@router.post("/detect-template-headings/{document_id}")
def detect_template_headings_endpoint(
    document_id: int,
    user_id: int = Query(...),
) -> JSONResponse:
    """
    Returns the list of detected headings based on template matching.
    Useful for Flutter frontend to preview what will be corrected.
    """
    conn = get_db()
    try:
        matches = detect_headings_from_template(document_id, user_id, conn)
        return JSONResponse(content={
            "document_id": document_id,
            "matches": matches
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Apply Paragraph Style (bulk)
# ─────────────────────────────────────────────────────────────────────────────

class ApplyParagraphStyleRequest(BaseModel):
    para_indices: Optional[List[int]] = None  # None = apply to ALL non-heading paragraphs


@router.post("/apply-paragraph-style/{document_id}")
def apply_paragraph_style(
    document_id: int,
    user_id: int = Query(...),
    body: ApplyParagraphStyleRequest = Body(default=ApplyParagraphStyleRequest()),
) -> JSONResponse:
    """Apply the template's paragraph style to specified (or all) body paragraphs."""
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    _ensure_docx(file_path, "apply-paragraph-style")

    rules    = _parse_formatting_rules(template)
    expected = _paragraph_style(rules)

    wc   = _make_working_copy(document_id, file_path)
    docx = Document(wc)

    count = 0
    for i, para in enumerate(docx.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        # KEY FIX: use _detect_heading_level() so font-size headings are also skipped
        if _detect_heading_level(para) is not None:
            continue
        if _is_toc_paragraph(para):
            continue
        if body.para_indices is not None and i not in body.para_indices:
            continue

        _apply_style_to_para(para, expected)
        count += 1

    docx.save(wc)

    return JSONResponse(content={
        "status":  "ok",
        "message": f"Paragraph style applied to {count} paragraph(s).",
        "applied": expected,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 7. Apply TOC Style (to existing TOC entries)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/apply-toc-style/{document_id}")
def apply_toc_style(
    document_id: int,
    user_id: int = Query(...),
) -> JSONResponse:
    """
    Applies standard Word TOC styles (TOC 1 / TOC 2 / TOC 3) to any paragraphs
    already detected as TOC entries.
    """
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    _ensure_docx(file_path, "apply-toc-style")

    rules = _parse_formatting_rules(template)
    toc_font = rules.get("toc_font", rules.get("body_font", "Times New Roman"))
    toc_size = rules.get("toc_size", rules.get("body_size", 11))

    wc   = _make_working_copy(document_id, file_path)
    docx = Document(wc)

    toc_paras_found = 0
    for para in docx.paragraphs:
        if not _is_toc_paragraph(para):
            continue
        toc_paras_found += 1
        text = para.text.strip()

        # Determine TOC depth from leading number e.g. "1.2.3  Title .. 5" → level 3
        depth_match = re.match(r"^(\d+(?:\.\d+)*)", text)
        depth = min(depth_match.group(1).count(".") + 1, 3) if depth_match else 1

        try:
            para.style = docx.styles[f"TOC {depth}"]
        except Exception:
            # Style not in doc — apply font manually
            for run in para.runs:
                run.font.name = toc_font
                run.font.size = Pt(toc_size)

    if toc_paras_found == 0:
        return JSONResponse(
            status_code=409,
            content={
                "status": "no_toc_found",
                "message": (
                    "No Table of Contents entries were detected in this document. "
                    "Use the 'Add TOC' button to insert one first, or open in "
                    "Word → References → Table of Contents → Insert Table of Contents."
                ),
            },
        )

    docx.save(wc)

    return JSONResponse(content={
        "status":             "ok",
        "message":            f"TOC styles applied to {toc_paras_found} TOC paragraph(s).",
        "toc_paras_updated":  toc_paras_found,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 8. Add TOC (NEW — inserts a complete TOC block)
# ─────────────────────────────────────────────────────────────────────────────

class AddTocRequest(BaseModel):
    title: Optional[str] = "Table of Contents"
    include_page_numbers: Optional[bool] = True


@router.post("/add-toc/{document_id}")
def add_toc(
    document_id: int,
    user_id: int = Query(...),
    body: AddTocRequest = Body(default=AddTocRequest()),
) -> JSONResponse:
    """
    Inserts a Table of Contents block at the beginning of the document
    (after the title/cover page if one exists).

    The TOC is built from all Heading 1/2/3 paragraphs already in the document.
    Each entry is formatted as:
        Heading Text ........................ (page placeholder)

    Styling follows the template rules (toc_font / body_font, toc_size / body_size).

    After inserting, the TOC entries are styled with Word "TOC 1/2/3" styles.
    """
    doc_row, template, file_path = _get_doc_and_template(document_id, user_id)
    _ensure_docx(file_path, "add-toc")

    rules    = _parse_formatting_rules(template)
    toc_font = rules.get("toc_font", rules.get("body_font", "Times New Roman"))
    toc_size = rules.get("toc_size", rules.get("body_size", 11))

    # ── KEY FIX: Scan the WORKING COPY for headings ──────────────────────────
    wc_path = _working_copy_path(document_id)
    if not os.path.exists(wc_path):
        # If no working copy exists, create one from the original
        _make_working_copy(document_id, file_path)
    
    wc = wc_path
    docx = Document(wc)

    # Check if TOC already exists
    has_existing_toc = any(_is_toc_paragraph(p) for p in docx.paragraphs)
    if has_existing_toc:
        return JSONResponse(
            status_code=409,
            content={
                "status":  "toc_exists",
                "message": "A Table of Contents already exists in this document. Use 'Apply TOC Style' to fix its formatting.",
            },
        )

    # Collect headings using robust detection (style + font size)
    # Guard: skip cover-page paragraphs and long body paragraphs
    headings = []
    seen_first_real_heading = False
    cover_page_end = _find_cover_page_end_index(docx)
    print(f"[TOC] cover_page_end={cover_page_end}")

    for i, para in enumerate(docx.paragraphs):
        lvl = _detect_heading_level(para)
        if lvl is not None and para.text.strip():
            text = para.text.strip()
            norm = _norm_text(text)

            # Guard 1 ─ cover-page index boundary
            if i < cover_page_end:
                print(f"[TOC] Suppressing cover-page para {i}: {text!r}")
                continue

            # Guard 2 ─ length check (body text cannot be a heading)
            if len(text) > 200:
                print(f"[TOC] Suppressing long para {i} ({len(text)} chars)")
                continue

            # Guard 5 ─ 'Label: explanation sentence' body bullets
            if ':' in text:
                after_colon = text.split(':', 1)[1].strip()
                if len(after_colon.split()) > 8:
                    print(f"[TOC] Suppressing label:sentence para {i}: {text[:60]!r}")
                    continue

            # Guard 3 ─ cover-page text patterns (catch anything the index missed)
            if not seen_first_real_heading:
                if norm in ("abstract", "introduction"):
                    seen_first_real_heading = True
                elif _is_cover_page_suppress(text):
                    print(f"[TOC] Suppressing cover-page noise: {text!r}")
                    continue

            headings.append({"text": text, "level": lvl})

    print(f"[TOC] Found {len(headings)} headings in working copy for TOC generation")


    if not headings:
        return JSONResponse(
            status_code=422,
            content={
                "status":  "no_headings",
                "message": "No headings found in this document. Add headings before generating a TOC.",
            },
        )

    # ── Find insertion point ──────────────────────────────────────────────────
    # Insert after first page-break or after first non-empty paragraph if no page break
    body_elem      = docx.element.body
    all_para_elems = list(body_elem.iterchildren(qn("w:p")))

    insert_after_idx = 0
    found_break = False
    for i, p_elem in enumerate(all_para_elems):
        xml_str = etree.tostring(p_elem, encoding="unicode")
        # Check for page break (w:br type="page" or lastRenderedPageBreak)
        if "w:lastRenderedPageBreak" in xml_str or 'w:type="page"' in xml_str or '<w:br' in xml_str and 'w:type="page"' in xml_str:
            insert_after_idx = i + 1
            print(f"[TOC] Found first page break at paragraph index {i}. Inserting TOC after it.")
            found_break = True
            break
        
    if not found_break:
        # Fallback: find the first non-empty paragraph (likely title/cover page content)
        for i, para in enumerate(docx.paragraphs):
            if para.text.strip():
                insert_after_idx = i + 1
                print(f"[TOC] No page break found. Inserting after first content paragraph at index {i}.")
                break

    # ── Build TOC title paragraph ─────────────────────────────────────────────
    toc_title_elem = OxmlElement("w:p")
    ref_elem       = all_para_elems[insert_after_idx] if insert_after_idx < len(all_para_elems) else None

    if ref_elem is not None:
        body_elem.insert(list(body_elem).index(ref_elem), toc_title_elem)
    else:
        sect_pr = body_elem.find(qn("w:sectPr"))
        if sect_pr is not None:
            body_elem.insert(list(body_elem).index(sect_pr), toc_title_elem)
        else:
            body_elem.append(toc_title_elem)

    from docx.text.paragraph import Paragraph as DocxParagraph
    toc_title_para = DocxParagraph(toc_title_elem, docx)
    toc_title_para.text = "Table of Contents"
    try:
        toc_title_para.style = docx.styles["TOC Heading"]
    except Exception:
        run = toc_title_para.runs[0] if toc_title_para.runs else toc_title_para.add_run("Table of Contents")
        run.font.bold = True
        run.font.size = Pt(toc_size + 2)
        run.font.name = toc_font

    # ── Insert TOC entry paragraphs ───────────────────────────────────────────
    inserted_elems = [toc_title_elem]

    for h in headings:
        dots_count = max(3, 60 - len(h["text"]) - (h["level"] - 1) * 4)
        entry_text = ("    " * (h["level"] - 1)) + h["text"] + " " + ("." * dots_count) + " 1"

        entry_elem = OxmlElement("w:p")
        last_inserted = inserted_elems[-1]
        idx_in_body   = list(body_elem).index(last_inserted)
        body_elem.insert(idx_in_body + 1, entry_elem)
        inserted_elems.append(entry_elem)

        entry_para = DocxParagraph(entry_elem, docx)
        entry_para.text = entry_text

        depth = min(h["level"], 3)
        try:
            entry_para.style = docx.styles[f"TOC {depth}"]
        except Exception:
            run = entry_para.runs[0] if entry_para.runs else entry_para.add_run(entry_text)
            run.font.name = toc_font
            run.font.size = Pt(toc_size)

    # ── Add a page-break after TOC so it sits on its own page ────────────────
    page_break_elem = OxmlElement("w:p")
    last_elem       = inserted_elems[-1]
    body_elem.insert(list(body_elem).index(last_elem) + 1, page_break_elem)

    pb_para = DocxParagraph(page_break_elem, docx)
    pb_run  = pb_para.add_run()
    br_elem = OxmlElement("w:br")
    br_elem.set(qn("w:type"), "page")
    pb_run._r.append(br_elem)

    docx.save(wc)

    return JSONResponse(content={
        "status":         "ok",
        "message":        f"Table of Contents inserted with {len(headings)} entries.",
        "entry_count":    len(headings),
        "toc_font":       toc_font,
        "toc_size":       toc_size,
    })