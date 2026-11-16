"""
table_numbering_service.py — Idempotent table numbering (global or chapter-wise).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from docx_tools.docx_fields import (
    _element_is_before_body_start,
    _heading_level_from_paragraph,
    rebuild_caption_with_seq,
)
from services.table_caption_service import (
    _uniquify_title,
    ensure_caption_at_position,
    find_caption_near_table,
    resolve_table_title,
    set_plain_table_caption_text,
)
from services.table_config import format_table_caption_label, get_table_format_config

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


def _iter_body_tables(doc):
    for table in doc.tables:
        if _element_is_before_body_start(doc, table._tbl):
            continue
        yield table


def assign_table_numbers(
    doc,
    formatting_rules: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Assign sequential numbers in document order (no mutation yet)."""
    cfg = get_table_format_config(formatting_rules)
    captioned = cfg["captioned"]
    scheme = captioned["numbering_scheme"]
    pattern = captioned["caption_format_pattern"]
    assignments: List[Dict[str, Any]] = []

    # Build chapter map by walking body elements in order
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    current_chapter = 1
    chapter_seq = 0
    global_n = 0
    tbl_i = 0
    h1_count = 0
    para_chapter: Dict[int, int] = {}

    body = doc.element.body
    for child in list(body):
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            level = _heading_level_from_paragraph(para)
            if level == 1:
                h1_count += 1
                text_num = _CHAPTER_NUM_RE.match((para.text or "").strip())
                if text_num:
                    current_chapter = max(h1_count, int(text_num.group(1)))
                else:
                    current_chapter = max(1, h1_count)
                chapter_seq = 0
            continue

        if child.tag != qn("w:tbl"):
            continue
        # Match python-docx Table object
        table = None
        for t in doc.tables:
            if t._tbl is child:
                table = t
                break
        if table is None:
            continue
        if _element_is_before_body_start(doc, table._tbl):
            continue

        table_id = f"tbl{tbl_i}"
        tbl_i += 1

        if scheme == "chapter":
            chapter_seq += 1
            n = chapter_seq
            chapter = current_chapter
        else:
            global_n += 1
            n = global_n
            chapter = None

        label = format_table_caption_label(
            pattern=pattern,
            n=n,
            chapter=chapter,
            description="",
        )
        assignments.append(
            {
                "table_id": table_id,
                "n": n,
                "chapter": chapter,
                "scheme": scheme,
                "label_prefix": label,
                "_table": table,
            }
        )

    if scheme == "chapter":
        assignments = _recount_chapters_by_h1_order(doc, assignments, pattern)

    return assignments


def _recount_chapters_by_h1_order(
    doc, assignments: List[Dict[str, Any]], pattern: str
) -> List[Dict[str, Any]]:
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    tbl_to_chapter: Dict[int, int] = {}
    h1_count = 0
    current_chapter = 1
    body = doc.element.body
    for child in list(body):
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            level = _heading_level_from_paragraph(para)
            if level == 1:
                h1_count += 1
                text_num = _CHAPTER_NUM_RE.match((para.text or "").strip())
                if text_num:
                    current_chapter = max(h1_count, int(text_num.group(1)))
                else:
                    current_chapter = max(1, h1_count)
            continue
        if child.tag == qn("w:tbl"):
            tbl_to_chapter[id(child)] = max(1, current_chapter)

    per_chapter: Dict[int, int] = {}
    out: List[Dict[str, Any]] = []
    for a in assignments:
        table = a["_table"]
        ch = tbl_to_chapter.get(id(table._tbl), a.get("chapter") or 1)
        per_chapter[ch] = per_chapter.get(ch, 0) + 1
        n = per_chapter[ch]
        label = format_table_caption_label(
            pattern=pattern, n=n, chapter=ch, description=""
        )
        out.append({**a, "n": n, "chapter": ch, "label_prefix": label})
    return out


def apply_numbering_to_table_captions(
    doc,
    assignments: List[Dict[str, Any]],
    formatting_rules: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    Write assigned numbers into caption paragraphs.
    Creates captions when table_require_caption is true.
    """
    cfg = get_table_format_config(formatting_rules)
    captioned = cfg["captioned"]
    preferred = captioned["caption_position"]
    require_caption = bool(captioned.get("require_caption", True))
    pattern = captioned["caption_format_pattern"]
    scheme = captioned["numbering_scheme"]
    applied: List[Dict[str, Any]] = []
    used_titles: set = set()

    for a in assignments:
        table = a["_table"]
        cap_para, _pos, raw = find_caption_near_table(doc, table)
        title, source = resolve_table_title(table, doc)
        desc = _uniquify_title(title, used_titles) if title else ""
        print(
            f"[caption] table={a['table_id']} source={source} "
            f"title={desc or '(none)'}"
        )

        create = require_caption
        cap_para, position, created = ensure_caption_at_position(
            doc,
            table,
            preferred_position=preferred,
            description=desc,
            create_if_missing=create,
        )

        label = format_table_caption_label(
            pattern=pattern,
            n=int(a["n"]),
            chapter=a.get("chapter"),
            description=desc,
        )

        caption_updated = False
        if cap_para is not None:
            if scheme == "global":
                rebuild_caption_with_seq(
                    cap_para, "Table", desc or " ", number=int(a["n"])
                )
            else:
                set_plain_table_caption_text(cap_para, label)
            caption_updated = True

        applied.append(
            {
                "table_id": a["table_id"],
                "n": a["n"],
                "chapter": a.get("chapter"),
                "scheme": a["scheme"],
                "label": label,
                "caption_updated": caption_updated,
                "caption_created": created,
                "caption_description": desc,
                "caption_position": position,
            }
        )

    return applied
