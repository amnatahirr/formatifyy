import re
from typing import List, Dict, Any, Optional
from docx import Document

# Lazy loading for heavy AI dependencies
_model = None
_embedding_cache = {}

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            return None
    return _model

def _get_embedding(model, text):
    global _embedding_cache
    if text not in _embedding_cache:
        _embedding_cache[text] = model.encode(text, convert_to_tensor=True)
    return _embedding_cache[text]

def _cosine_sim(model, text1: str, text2: str) -> float:
    """Calculates cosine similarity between two strings."""
    from sentence_transformers import util
    emb1 = _get_embedding(model, text1)
    emb2 = _get_embedding(model, text2)
    return float(util.cos_sim(emb1, emb2))

def _normalise(text: str) -> str:
    """Strip trailing punctuation and lowercase."""
    return re.sub(r'[:\.\?\!]+$', '', text.strip()).lower()

def _contains_match(para_norm: str, heading_norm: str) -> bool:
    """
    True if heading_norm appears in para_norm AND no meaningful word
    precedes it in the paragraph.

    This prevents 'Project Objectives' from matching template heading
    'Objectives': the word 'Project' before 'Objectives' is meaningful
    and signals a different (sub-)section.

    Stop-words (articles, prepositions, conjunctions) before the heading
    text are ignored so 'Objectives and Scope of the Project' still
    matches 'Objectives' (heading appears at position 0).
    """
    if heading_norm not in para_norm:
        return False
    idx = para_norm.index(heading_norm)
    words_before = para_norm[:idx].strip().split()
    _STOP = {"and", "or", "of", "the", "a", "an", "for", "in", "on", "to", "&"}
    meaningful_before = [w for w in words_before if w not in _STOP]
    return len(meaningful_before) == 0


def _is_label_colon_body(text: str) -> bool:
    """
    Guard 5 — 'Label: explanation sentence' detector.

    Returns True when the paragraph is a BODY bullet/list item that
    starts with a short label, a colon, then a continuation sentence.
    Such paragraphs are NEVER section headings.

    Rule: text contains ':'  AND  the part after the FIRST colon has
    more than 8 words.

    Examples that return True  (body text → skip heading style):
      'Admin Panel: It allows administrators to post and control ...'
      'AI-Powered Content Classification: Detecting attributes ...'
      'Consistency and Accuracy: With automated formatting, ...'
      'Time Savings: The automation of the repetitive format ...'

    Examples that return False  (real headings → allow heading style):
      'Abstract:'              → nothing after colon
      'Related Work:'         → nothing after colon
      'Background'            → no colon
      'Problem Statement'     → no colon
    """
    if ':' not in text:
        return False
    after_colon = text.split(':', 1)[1].strip()
    return len(after_colon.split()) > 8


def _find_title_page_end(doc) -> int:
    """
    Returns the index of the last front-matter paragraph (inclusive).
    The detection loop uses  ``if i <= title_page_end: continue``  so every
    paragraph up to and including this index is skipped.

    Priority:
      1. Hard page break  (most reliable — never mis-fires)
      2. Text-based scan  — find the first paragraph whose stripped,
         normalised text is 'abstract' or 'introduction'.  Everything
         before that paragraph is cover-page content.
    """
    from docx.oxml.ns import qn
    import re as _re

    page_break_indices = []
    for i, para in enumerate(doc.paragraphs):
        for br in para._element.iter(qn("w:br")):
            if br.get(qn("w:type")) == "page":
                page_break_indices.append(i)
                break
    if page_break_indices:
        return min(page_break_indices)

    # Fallback: text-based scan for the first real section heading
    for i, para in enumerate(doc.paragraphs):
        t = _re.sub(r'[^a-z]', '', para.text.strip().lower())
        if t in ('abstract', 'introduction'):
            # Return i-1 so the cover-page guard skips 0 .. i-1
            # and includes i (the abstract heading) in detection.
            return max(0, i - 1)

    return 0  # no front-matter detected

def detect_headings_v2_from_doc(doc: Document, sections_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Same as detect_headings_v2 but accepts an open python-docx Document."""
    title_page_end = _find_title_page_end(doc)
    return _run_detection(doc, sections_list, title_page_end)

def detect_headings_v2(docx_path: str, template_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """File-path entry point — opens doc then delegates."""
    try:
        doc = Document(docx_path)
    except Exception:
        return {
            "foundHeadings": [],
            "missingStyleHeadings": [],
            "wronglyStyledParagraphs": [],
            "truelyMissing": []
        }
    return detect_headings_v2_from_doc(doc, template_sections)

def _run_detection(doc: Document, template_sections: List[Dict[str, Any]], title_page_end: int) -> Dict[str, Any]:
    """Internal core detection logic using greedy matching with tiers."""
    sections = [s["name"] for s in template_sections]
    SYNONYMS = {s["name"]: s.get("aliases", []) for s in template_sections}
    remaining_sections = list(sections)  # consumed as headings are found

    found_headings_dict = {}
    missing_style_headings_dict = {}
    wrongly_styled = []

    model = _get_model()
    total_sections = len(sections)

    for i, para in enumerate(doc.paragraphs):
        if i <= title_page_end:
            continue

        para_text = para.text.strip()
        if not para_text:
            continue

        # ── Guard: real section headings are never 200+ characters ──────────
        # A 200-char limit rules out all body paragraphs (the abstract body
        # alone is 1 900+ chars) while comfortably fitting every realistic
        # heading (the longest template heading here is 42 chars).
        if len(para_text) > 200:
            # If this long paragraph already carries a Heading style it was
            # incorrectly styled — flag it for reversion.
            if (para.style and para.style.name and
                    para.style.name.startswith("Heading")):
                wrongly_styled.append({
                    "paraIndex": i,
                    "text": para_text[:80],
                    "currentStyle": para.style.name,
                })
            continue

        # ── Guard 5: 'Label: explanation sentence' ─ body text, not a heading ─
        if _is_label_colon_body(para_text):
            if (para.style and para.style.name and
                    para.style.name.startswith("Heading")):
                wrongly_styled.append({
                    "paraIndex": i,
                    "text": para_text[:80],
                    "currentStyle": para.style.name,
                })
            continue

        # Stop early once all sections have been matched
        if not remaining_sections:
            break

        norm = _normalise(para_text)

        matched_heading = None
        matched_tier = None

        for heading in list(remaining_sections):
            h_norm = _normalise(heading)
            # Tier 1: exact
            if norm == h_norm:
                matched_heading = heading
                matched_tier = "exact"
                break
            # Tier 2: contains
            if _contains_match(norm, h_norm):
                matched_heading = heading
                matched_tier = "contains"
                break
            # Tier 3: synonym
            for alias in SYNONYMS.get(heading, []):
                if norm == _normalise(alias):
                    matched_heading = heading
                    matched_tier = "synonym"
                    break
            if matched_heading:
                break

        # Tier 4: semantic — only if no tier 1-3 match found
        if not matched_heading and model is not None:
            best_score = 0.0
            best_candidate = None
            for heading in remaining_sections:
                score = _cosine_sim(model, norm, _normalise(heading))
                if score > best_score:
                    best_score = score
                    best_candidate = heading
            if best_score >= 0.35:
                matched_heading = best_candidate
                matched_tier = "semantic"
            else:
                if best_candidate:
                    print(
                        f"[HeadingDetect] NO MATCH: Para {i} \"{para_text[:60]}\" "
                        f"vs \"{best_candidate}\" => score={best_score:.3f}"
                    )

        if matched_heading:
            remaining_sections.remove(matched_heading)
            print(
                f"[HeadingDetect] MATCH: Para {i} -> \"{matched_heading}\" ({matched_tier})"
            )
            is_heading_style = bool(
                para.style and para.style.name and
                para.style.name.startswith("Heading")
            )
            if is_heading_style:
                found_headings_dict[matched_heading] = {
                    "paraIndex": i,
                    "matchType": matched_tier,
                    "styleCorrect": True,
                }
            else:
                missing_style_headings_dict[matched_heading] = {
                    "paraIndex": i,
                    "matchType": matched_tier,
                    "currentStyle": para.style.name if para.style else "Normal",
                    "styleCorrect": False,
                }
        elif (
            para.style and para.style.name and
            para.style.name.startswith("Heading")
        ):
            # Wrongly styled: has Heading style but not matched to any template
            # heading. Catches short paragraphs like 'Project Objectives'.
            wrongly_styled.append({
                "paraIndex": i,
                "text": para_text[:80],
                "currentStyle": para.style.name,
            })

    found_count = len(found_headings_dict) + len(missing_style_headings_dict)
    print(
        f"[HeadingDetect] Summary: {found_count}/{total_sections} headings found"
    )

    return {
        "foundHeadings": found_headings_dict,
        "missingStyleHeadings": missing_style_headings_dict,
        "wronglyStyledParagraphs": wrongly_styled,
        "truelyMissing": remaining_sections,
    }
