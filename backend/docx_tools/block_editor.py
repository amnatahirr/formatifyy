"""
Apply edited preview blocks back onto a DOCX working copy.

The preview panel shows ``build_preview_elements`` output (heading / paragraph /
list_item / image / table).  When the user edits text in that panel we get the
full block list back.  We diff it against what the preview produced for the
current file and apply only the text changes, so fonts, images, tables, page
setup etc. stay exactly as they were.
"""
from __future__ import annotations

import copy
import difflib
import re
from typing import Any, Dict, List

from docx import Document
from docx.oxml.ns import qn

TEXT_TYPES = {"heading", "paragraph", "list_item"}


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _key(el: Dict[str, Any]) -> str:
    return f"{el.get('type', 'paragraph')}|{_norm(el.get('text'))}"


def _has_drawing(p) -> bool:
    return bool(p._p.xpath(".//w:drawing | .//w:pict | .//w:object"))


def _set_paragraph_text(p, text: str) -> None:
    """Replace the text but keep the first run's formatting and any drawings."""
    runs = p.runs
    target = None
    for r in runs:
        if r._r.findall(qn("w:t")):
            target = r
            break
    if target is None:
        p.add_run(text)
        return
    for r in runs:
        for t in r._r.findall(qn("w:t")):
            r._r.remove(t)
    parts = str(text).split("\n")
    for i, part in enumerate(parts):
        if i:
            target._r.append(target._r.makeelement(qn("w:br"), {}))
        t = target._r.makeelement(qn("w:t"), {})
        t.text = part
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        target._r.append(t)


def apply_block_edits(
    docx_path: str,
    original_elements: List[Dict[str, Any]],
    new_blocks: List[Dict[str, Any]],
) -> Dict[str, int]:
    """
    Diff ``new_blocks`` against ``original_elements`` and patch ``docx_path``.
    Returns counts: {"edited", "deleted", "inserted", "skipped"}.
    """
    doc = Document(docx_path)
    paras = list(doc.paragraphs)  # body-level paragraphs only (not table cells)
    stats = {"edited": 0, "deleted": 0, "inserted": 0, "skipped": 0}

    # Map each original text element -> a body paragraph, walking in order.
    para_for: Dict[int, Any] = {}
    cursor = 0
    for idx, el in enumerate(original_elements):
        if el.get("type", "paragraph") not in TEXT_TYPES:
            continue
        want = _norm(el.get("text"))
        if not want:
            continue
        for j in range(cursor, len(paras)):
            if _norm(paras[j].text) == want:
                para_for[idx] = paras[j]
                cursor = j + 1
                break

    sm = difflib.SequenceMatcher(
        a=[_key(e) for e in original_elements],
        b=[_key(e) for e in new_blocks],
        autojunk=False,
    )

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        olds = list(range(i1, i2))
        news = list(range(j1, j2))
        pair = min(len(olds), len(news))

        # paired -> text edits
        for k in range(pair):
            oi, nj = olds[k], news[k]
            o, n = original_elements[oi], new_blocks[nj]
            if o.get("type", "paragraph") not in TEXT_TYPES:
                stats["skipped"] += 1
                continue
            p = para_for.get(oi)
            if p is None or _has_drawing(p):
                stats["skipped"] += 1
                continue
            _set_paragraph_text(p, str(n.get("text") or ""))
            stats["edited"] += 1

        # leftover old -> deletions (text paragraphs only)
        for oi in olds[pair:]:
            o = original_elements[oi]
            p = para_for.get(oi)
            if o.get("type", "paragraph") in TEXT_TYPES and p is not None and not _has_drawing(p):
                p._p.getparent().remove(p._p)
                stats["deleted"] += 1
            else:
                stats["skipped"] += 1

        # leftover new -> insertions after the nearest preceding mapped paragraph
        anchor = None
        for oi in range(min(i2, len(original_elements)) - 1, -1, -1):
            if oi in para_for:
                anchor = para_for[oi]
                break
        for nj in news[pair:]:
            n = new_blocks[nj]
            if n.get("type", "paragraph") not in TEXT_TYPES:
                stats["skipped"] += 1
                continue
            if anchor is None:
                new_p = doc.add_paragraph(str(n.get("text") or ""))
                anchor = new_p
            else:
                new_el = copy.deepcopy(anchor._p)
                anchor._p.addnext(new_el)
                from docx.text.paragraph import Paragraph
                new_p = Paragraph(new_el, anchor._parent)
                for d in new_el.xpath(".//w:drawing | .//w:pict"):
                    d.getparent().remove(d)
                if not new_p.runs:
                    new_p.add_run("")
                _set_paragraph_text(new_p, str(n.get("text") or ""))
                anchor = new_p
            stats["inserted"] += 1

    doc.save(docx_path)
    return stats


def docx_from_blocks(path: str, blocks: List[Dict[str, Any]]) -> None:
    """Fallback for non-DOCX sources (PDF/TXT): build a plain DOCX from blocks."""
    doc = Document()
    for b in blocks:
        t = b.get("type", "paragraph")
        text = str(b.get("text") or "")
        if t not in TEXT_TYPES:
            continue
        if t == "heading":
            lvl = b.get("level")
            lvl = lvl if isinstance(lvl, int) and 1 <= lvl <= 9 else 1
            doc.add_heading(text, level=lvl)
        elif t == "list_item":
            doc.add_paragraph(text, style="List Bullet")
        else:
            doc.add_paragraph(text)
    doc.save(path)