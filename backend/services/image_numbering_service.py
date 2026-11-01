"""
image_numbering_service.py — Idempotent figure numbering (global or chapter-wise).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from docx_tools.docx_fields import (
    _heading_level_from_paragraph,
    is_paragraph_in_cover_or_info,
    paragraph_has_image,
    rebuild_caption_with_seq,
)
from services.image_caption_service import (
    _extract_description,
    _find_caption_near,
    _set_plain_caption_text,
)
from services.image_config import format_caption_label, get_image_format_config

_CHAPTER_NUM_RE = re.compile(r"^(\d+)")


def _chapter_number_from_heading_text(text: str, fallback: int) -> int:
    t = (text or "").strip()
    m = _CHAPTER_NUM_RE.match(t)
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            pass
    return fallback


def assign_figure_numbers(
    doc,
    formatting_rules: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    Assign sequential numbers in document order.
    Idempotent: recomputes from scratch each call (does not mutate captions yet).
    """
    cfg = get_image_format_config(formatting_rules)
    scheme = cfg["numbering_scheme"]
    assignments: List[Dict[str, Any]] = []

    current_chapter = 1
    chapter_seq = 0
    global_n = 0
    img_i = 0

    for para in doc.paragraphs:
        level = _heading_level_from_paragraph(para)
        if level == 1:
            current_chapter = _chapter_number_from_heading_text(para.text or "", current_chapter)
            # If heading has no leading number, increment chapter on each H1 after first image batch
            if not _CHAPTER_NUM_RE.match((para.text or "").strip()):
                # Use ordinal of H1s encountered
                pass
            chapter_seq = 0

        if not paragraph_has_image(para):
            continue
        # Cover / Project Details images are outside report figure numbering
        if is_paragraph_in_cover_or_info(doc, para):
            continue

        image_id = f"img{img_i}"
        img_i += 1

        if scheme == "chapter":
            chapter_seq += 1
            n = chapter_seq
            chapter = current_chapter
            label = format_caption_label(
                pattern=cfg["caption_format_pattern"],
                n=n,
                chapter=chapter,
                caption="",
            )
        else:
            global_n += 1
            n = global_n
            chapter = None
            label = format_caption_label(
                pattern=cfg["caption_format_pattern"],
                n=n,
                chapter=None,
                caption="",
            )

        assignments.append(
            {
                "image_id": image_id,
                "n": n,
                "chapter": chapter,
                "label_prefix": label.rstrip(": ").strip() if not label.endswith("{caption}") else label,
                "scheme": scheme,
                "_para": para,
            }
        )

    # Fix chapter ordinals when H1 texts lack numbers: recount H1 index
    if scheme == "chapter":
        assignments = _recount_chapters_by_h1_order(doc, assignments, cfg)

    return assignments


def _recount_chapters_by_h1_order(
    doc, assignments: List[Dict[str, Any]], cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Map each image to chapter = count of Heading 1s seen so far (min 1)."""
    para_to_chapter: Dict[int, int] = {}
    h1_count = 0
    for para in doc.paragraphs:
        level = _heading_level_from_paragraph(para)
        if level == 1:
            h1_count += 1
            text_num = _CHAPTER_NUM_RE.match((para.text or "").strip())
            if text_num:
                h1_count = max(h1_count, int(text_num.group(1)))
        if paragraph_has_image(para):
            para_to_chapter[id(para._element)] = max(1, h1_count or 1)

    # Re-seq within chapter
    per_chapter: Dict[int, int] = {}
    out: List[Dict[str, Any]] = []
    for a in assignments:
        para = a["_para"]
        ch = para_to_chapter.get(id(para._element), a.get("chapter") or 1)
        per_chapter[ch] = per_chapter.get(ch, 0) + 1
        n = per_chapter[ch]
        label = format_caption_label(
            pattern=cfg["caption_format_pattern"],
            n=n,
            chapter=ch,
            caption="",
        )
        out.append(
            {
                **a,
                "n": n,
                "chapter": ch,
                "label_prefix": label,
            }
        )
    return out


def apply_numbering_to_captions(
    doc,
    assignments: List[Dict[str, Any]],
    formatting_rules: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    Write assigned numbers into caption paragraphs (idempotent full rewrite).
    Creates no new captions when missing — only updates existing ones.
    Returns cleaned assignment dicts (no private para refs in API output).
    """
    cfg = get_image_format_config(formatting_rules)
    applied: List[Dict[str, Any]] = []

    for a in assignments:
        para = a["_para"]
        cap_para, _pos, raw = _find_caption_near(doc, para)
        desc = _extract_description(raw or "") if raw else ""

        label = format_caption_label(
            pattern=cfg["caption_format_pattern"],
            n=int(a["n"]),
            chapter=a.get("chapter"),
            caption=desc,
        )

        if cap_para is not None:
            if cfg["numbering_scheme"] == "global":
                rebuild_caption_with_seq(cap_para, "Figure", desc or " ")
            else:
                _set_plain_caption_text(cap_para, label)

        applied.append(
            {
                "image_id": a["image_id"],
                "n": a["n"],
                "chapter": a.get("chapter"),
                "scheme": a["scheme"],
                "label": label,
                "caption_updated": cap_para is not None,
                "caption_description": desc,
            }
        )

    return applied
