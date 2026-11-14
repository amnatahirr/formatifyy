"""Apply paragraph-level edits (and new images) to an existing .docx in place.

Only body paragraphs are touched. Tables, existing images, headers/footers and
all other parts of the document are left exactly as they are.

Op formats (paragraphs are found by their text + occurrence number):
  {"op": "replace", "match": "old text", "occurrence": 0, "text": "new text"}
  {"op": "delete",  "match": "old text", "occurrence": 0}
  {"op": "insert_after", "anchor": {"match": "...", "occurrence": 0} | None,
   "text": "new paragraph", "type": "paragraph"}
  {"op": "insert_image", "anchor": {"match": "...", "occurrence": 0} | None,
   "file_index": 0}          # anchor None = end of document
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph

def _norm(s: str) -> str:
    return " ".join((s or "").replace("\xa0", " ").split()).casefold()

def _has_drawing(run) -> bool:
    return bool(run._r.xpath(".//w:drawing") or run._r.xpath(".//w:pict"))


def _para_has_drawing(p: Paragraph) -> bool:
    return any(_has_drawing(r) for r in p.runs)


def _set_text(p: Paragraph, text: str) -> None:
    """Replace the text but keep the first run's formatting (and any images)."""
    runs = [r for r in p.runs if not _has_drawing(r)]
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r.text = ""
    else:
        p.add_run(text)


def _clone_paragraph(src: Paragraph, text: str) -> Paragraph:
    new_p = deepcopy(src._p)
    for child in list(new_p):
        if child.tag != qn("w:pPr"):
            new_p.remove(child)
    para = Paragraph(new_p, src._parent)
    run = para.add_run(text)
    first = next((r for r in src.runs if not _has_drawing(r)), None)
    if first is not None and first._r.rPr is not None:
        run._r.insert(0, deepcopy(first._r.rPr))
    return para


def apply_text_edits(
    src_path: str,
    dst_path: str,
    ops: List[Dict[str, Any]],
    image_paths: Optional[List[str]] = None,
) -> Dict[str, int]:
    image_paths = image_paths or []
    doc = Document(src_path)

    # Index body paragraphs by their text (before any change is made).
    index: Dict[str, List[Paragraph]] = {}
    ordered: List[tuple] = []
    for p in doc.paragraphs:
        t = _norm(p.text)
        if t:
            index.setdefault(t, []).append(p)
            ordered.append((t, p))

    def find(ref: Optional[Dict[str, Any]]) -> Optional[Paragraph]:
        if not ref:
            return None
        key = _norm(str(ref.get("match", "")))
        if not key:
            return None
        try:
            occ = int(ref.get("occurrence", 0))
        except (TypeError, ValueError):
            occ = 0

        # 1) exact (normalized) match
        lst = index.get(key, [])
        if 0 <= occ < len(lst):
            return lst[occ]
        if lst:
            return lst[-1]

        # 2) fuzzy fallback: one text contains the other (numbering/prefix differences)
        hits = [p for t, p in ordered if key in t or t in key]
        if hits:
            return hits[min(max(occ, 0), len(hits) - 1)]
        return None

    # Resolve every target first, so earlier edits can't shift later lookups.
    resolved = []
    for op in ops:
        kind = op.get("op")
        if kind in ("insert_after", "insert_image"):
            resolved.append((op, find(op.get("anchor"))))
        else:
            resolved.append((op, find(op)))

    first_para = doc.paragraphs[0] if doc.paragraphs else None
    stats = {"replaced": 0, "deleted": 0, "inserted": 0, "images": 0}
    cursors: Dict[int, Any] = {}  # id(anchor paragraph) -> last inserted <w:p>
    start_cursor = None

    for op, target in resolved:
        kind = op.get("op")
        text = str(op.get("text", ""))

        if kind == "replace" and target is not None:
            _set_text(target, text)
            stats["replaced"] += 1

        elif kind == "delete" and target is not None:
            if _para_has_drawing(target):
                _set_text(target, "")  # keep the image, drop the text
            else:
                target._p.getparent().remove(target._p)
            stats["deleted"] += 1

        elif kind == "insert_after":
            template = target if target is not None else first_para
            if template is None:
                doc.add_paragraph(text)
                stats["inserted"] += 1
                continue

            new_para = _clone_paragraph(template, text)

            # New plain paragraphs should not inherit a heading style.
            if str(op.get("type", "paragraph")) == "paragraph":
                style_name = (template.style.name if template.style is not None else "") or ""
                if style_name.lower().startswith(("heading", "title")):
                    try:
                        new_para.style = doc.styles["Normal"]
                    except KeyError:
                        pass

            if target is not None:
                key = id(target)
                cursor = cursors.get(key, target._p)
                cursor.addnext(new_para._p)
                cursors[key] = new_para._p
            else:
                # Before the first paragraph of the document.
                if start_cursor is None:
                    template._p.addprevious(new_para._p)
                else:
                    start_cursor.addnext(new_para._p)
                start_cursor = new_para._p
            stats["inserted"] += 1

        elif kind == "insert_image":
            try:
                idx = int(op.get("file_index", -1))
            except (TypeError, ValueError):
                continue
            if not (0 <= idx < len(image_paths)):
                continue

            if op.get("anchor") and target is None:
                stats["image_anchor_missing"] = stats.get("image_anchor_missing", 0) + 1
                print(f"[doc_edit] image anchor not found: {op.get('anchor')}", flush=True)
                continue   # end par mat daalo

            try:
                pic_para = doc.add_paragraph()
                pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pic_para.add_run().add_picture(image_paths[idx], width=Inches(5))
            except Exception:
                continue

            if target is not None and target._p.getparent() is not None:
                key = id(target)
                cursor = cursors.get(key, target._p)
                cursor.addnext(pic_para._p)
                cursors[key] = pic_para._p
            stats["images"] += 1

    doc.save(dst_path)
    return stats