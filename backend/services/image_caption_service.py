"""
image_caption_service.py — Detect / standardize figure captions near images.

Does NOT invent caption prose. Missing captions are flagged only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from docx_tools.docx_fields import (
    is_paragraph_in_cover_or_info,
    paragraph_has_image,
    paragraph_has_seq_caption,
    paragraph_is_figure_caption,
)
from services.image_config import get_image_format_config

_CAPTION_LIKE_RE = re.compile(
    r"^(figure|fig\.?|image)\b[\s.:\-]*",
    re.IGNORECASE,
)
_CAPTION_NUMBER_RE = re.compile(
    r"^(?:figure|fig\.?)\s*(\d+(?:\.\d+)*)?\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
_SHORT_CAPTION_MAX_CHARS = 220
_SHORT_CAPTION_MAX_WORDS = 40


def _prev_body_paragraphs(doc, img_para, limit: int = 3):
    el = img_para._element.getprevious()
    seen = 0
    while el is not None and seen < limit:
        if el.tag == qn("w:p"):
            yield Paragraph(el, img_para._parent)
            seen += 1
        el = el.getprevious()


def _next_body_paragraphs(doc, img_para, limit: int = 3):
    from docx_tools.docx_fields import _next_body_paragraphs as _nxt

    yield from _nxt(doc, img_para, limit=limit)


def _looks_like_caption(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > _SHORT_CAPTION_MAX_CHARS:
        return False
    if len(t.split()) > _SHORT_CAPTION_MAX_WORDS:
        return False
    return bool(_CAPTION_LIKE_RE.match(t))


def _extract_description(text: str) -> str:
    t = (text or "").strip()
    m = _CAPTION_NUMBER_RE.match(t)
    if m:
        return (m.group(2) or "").strip()
    if ":" in t:
        return t.split(":", 1)[1].strip()
    return _CAPTION_LIKE_RE.sub("", t).strip(" :.-")


def _find_caption_near(
    doc, img_para
) -> Tuple[Optional[Paragraph], Optional[str], Optional[str]]:
    """
    Returns (caption_para, position 'below'|'above', raw_text).

    Prefer caption immediately below the image. A caption immediately above is
    only accepted when it is not already the below-caption of a previous image.
    """
    for cand in _next_body_paragraphs(doc, img_para, limit=2):
        if paragraph_has_image(cand):
            break
        text = (cand.text or "").strip()
        if paragraph_is_figure_caption(cand) or _looks_like_caption(text):
            return cand, "below", text

    # Only the immediately preceding paragraph may be an "above" caption.
    for cand in _prev_body_paragraphs(doc, img_para, limit=1):
        if paragraph_has_image(cand):
            break
        # If the paragraph before `cand` is an image, `cand` belongs to that image.
        owned_by_prev = False
        for before in _prev_body_paragraphs(doc, cand, limit=1):
            if paragraph_has_image(before):
                owned_by_prev = True
            break
        if owned_by_prev:
            break
        text = (cand.text or "").strip()
        if paragraph_is_figure_caption(cand) or _looks_like_caption(text):
            return cand, "above", text

    return None, None, None


def _pattern_is_valid(text: str, numbering_scheme: str, cap_para=None) -> bool:
    t = (text or "").strip()
    if numbering_scheme == "chapter":
        return bool(re.match(r"^Figure\s+\d+\.\d+\s*:", t, re.IGNORECASE))
    if cap_para is not None and paragraph_has_seq_caption(cap_para._element, "Figure"):
        return True
    return bool(re.match(r"^Figure\s+\d+\s*:", t, re.IGNORECASE)) or bool(
        re.match(r"^Figure\s*:", t, re.IGNORECASE)
    )


def detect_captions_for_document(
    doc,
    formatting_rules: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Analyze captions for every embedded image (document order). No mutation."""
    cfg = get_image_format_config(formatting_rules)
    results: List[Dict[str, Any]] = []
    img_i = 0

    for para in doc.paragraphs:
        if not paragraph_has_image(para):
            continue
        # Skip Cover / Project Details images entirely
        if is_paragraph_in_cover_or_info(doc, para):
            continue
        image_id = f"img{img_i}"
        img_i += 1

        cap_para, position, raw = _find_caption_near(doc, para)
        issues: List[str] = []
        caption_found = cap_para is not None and bool(raw)
        caption_missing = not caption_found
        format_valid = False
        caption_text = raw or ""

        if caption_missing:
            issues.append("caption_missing")
        else:
            format_valid = _pattern_is_valid(
                caption_text, cfg["numbering_scheme"], cap_para
            )
            if not format_valid:
                issues.append("caption_format_inconsistent")
            preferred = cfg["caption_position"]
            if position and position != preferred:
                issues.append(f"caption_position_is_{position}_expected_{preferred}")

        results.append(
            {
                "image_id": image_id,
                "caption_found": caption_found,
                "caption_missing": caption_missing,
                "caption_text": caption_text,
                "caption_description": _extract_description(caption_text)
                if caption_text
                else "",
                "caption_position": position,
                "format_valid": format_valid,
                "issues": issues,
                "_para": para,
                "_cap_para": cap_para,
            }
        )

    return results


def _set_plain_caption_text(para, text: str) -> None:
    p_el = para._element
    for child in list(p_el):
        if child.tag != qn("w:pPr"):
            p_el.remove(child)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    run.append(t)
    p_el.append(run)
    try:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        pass
