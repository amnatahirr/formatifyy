"""
Apply edited preview blocks back onto a DOCX working copy.

The preview panel shows ``build_preview_elements`` output (heading / paragraph /
list_item / image / table).  When the user edits in that panel we get the full
block list back.  We diff it against what the preview produced for the current
file and apply only the changes, so fonts, existing images, tables, page setup
etc. stay exactly as they were.

Supported changes:
  * text edits / new / deleted text paragraphs
  * new images (``image_base64`` from the editor's "Insert image")
  * moved or deleted existing images (matched by ``image_index``)
"""
from __future__ import annotations

import base64
import copy
import difflib
import io
import re
from typing import Any, Dict, List, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Emu
from docx.text.paragraph import Paragraph

TEXT_TYPES = {"heading", "paragraph", "list_item"}

_A_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
_R_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _type(el: Dict[str, Any]) -> str:
    return str(el.get("type") or "paragraph").lower()


def _text(el: Dict[str, Any]) -> str:
    """The editor writes edits to ``corrected_text``; fall back to ``text``."""
    ct = el.get("corrected_text")
    if isinstance(ct, str):
        return ct
    return str(el.get("text") or el.get("title") or "")


def _image_index(el: Dict[str, Any]) -> Optional[int]:
    v = el.get("image_index")
    try:
        return int(v) if v is not None and str(v) != "" else None
    except (TypeError, ValueError):
        return None


def _key(el: Dict[str, Any], pos: int, side: str) -> str:
    t = _type(el)
    if t == "image":
        if el.get("image_base64"):
            return f"image|new|{side}{pos}"  # brand-new image never matches
        idx = _image_index(el)
        return f"image|{idx}" if idx is not None else f"image|path|{el.get('image_path')}"
    if t == "table":
        return f"table|{_norm(el.get('rows'))}"
    return f"{t}|{_norm(_text(el))}"


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


def _content_width(doc) -> int:
    try:
        s = doc.sections[-1]
        return int(s.page_width - s.left_margin - s.right_margin)
    except Exception:
        return int(Emu(5943600))  # 6.5in


def _map_elements(doc, original_elements):
    """
    Map each preview element to the body XML it came from.
    Returns (main, extra): main[idx] = the element's paragraph/table XML,
    extra[idx] = caption paragraph XML for images that absorbed one.
    """
    body = doc.element.body
    paras = [c for c in body.iterchildren() if c.tag == qn("w:p")]
    tables = [c for c in body.iterchildren() if c.tag == qn("w:tbl")]

    # image_index -> paragraph, counted exactly like preview_elements._para_images
    img_para: Dict[int, Any] = {}
    n = 0
    for p in paras:
        for blip in p.iter(_A_BLIP):
            rid = blip.get(_R_EMBED)
            if not rid or rid not in doc.part.related_parts:
                continue
            img_para[n] = p
            n += 1

    main: Dict[int, Any] = {}
    extra: Dict[int, Any] = {}
    cursor = 0
    tcursor = 0
    for idx, el in enumerate(original_elements):
        t = _type(el)
        if t == "image":
            ii = _image_index(el)
            p = img_para.get(ii) if ii is not None else None
            if p is None:
                continue
            main[idx] = p
            cap = _norm(el.get("caption"))
            if cap:
                nxt = p.getnext()
                while nxt is not None and nxt.tag == qn("w:p") and not _norm(Paragraph(nxt, doc).text):
                    nxt = nxt.getnext()
                if nxt is not None and nxt.tag == qn("w:p") and _norm(Paragraph(nxt, doc).text) == cap:
                    extra[idx] = nxt
                    if nxt in paras:
                        cursor = max(cursor, paras.index(nxt) + 1)
        elif t == "table":
            if tcursor < len(tables):
                main[idx] = tables[tcursor]
                tcursor += 1
        else:
            want = _norm(el.get("text"))
            if not want:
                continue
            for j in range(cursor, len(paras)):
                if _norm(Paragraph(paras[j], doc).text) == want:
                    main[idx] = paras[j]
                    cursor = j + 1
                    break
    return main, extra


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
    body = doc.element.body
    stats = {"edited": 0, "deleted": 0, "inserted": 0, "skipped": 0}

    main, extra = _map_elements(doc, original_elements)
    removed: set = set()

    def last_xml(oi: int):
        return extra.get(oi, main.get(oi))

    def is_editable_text(oi: int) -> bool:
        p = main.get(oi)
        return (
            _type(original_elements[oi]) in TEXT_TYPES
            and p is not None
            and p.tag == qn("w:p")
            and not _has_drawing(Paragraph(p, doc))
        )

    def template_for(block: Dict[str, Any]):
        """A paragraph to clone formatting from for a new text block."""
        t = _type(block)
        lvl = block.get("level")
        fallback = None
        for oi, el in enumerate(original_elements):
            if oi in removed or not is_editable_text(oi):
                continue
            if _type(el) == t and (t != "heading" or el.get("level") == lvl):
                return main[oi]
            if fallback is None and _type(el) == "paragraph":
                fallback = main[oi]
        return fallback

    def place(new_xml, anchor):
        if anchor is None:
            body.insert(0, new_xml)
        else:
            anchor.addnext(new_xml)
        return new_xml

    def new_text_para(block, anchor):
        text = _text(block)
        tpl = template_for(block)
        if tpl is not None:
            el = copy.deepcopy(tpl)
            for d in el.xpath(".//w:drawing | .//w:pict | .//w:object"):
                d.getparent().remove(d)
            place(el, anchor)
            p = Paragraph(el, doc._body)
            if not p.runs:
                p.add_run("")
            _set_paragraph_text(p, text)
            return el
        p = doc.add_paragraph(text)
        if _type(block) == "heading":
            try:
                p.style = doc.styles[f"Heading {int(block.get('level') or 1)}"]
            except Exception:
                pass
        return place(p._p, anchor)

    def caption_para(text, anchor):
        p = doc.add_paragraph()
        try:
            p.style = doc.styles["Caption"]
        except Exception:
            pass
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.italic = True
        return place(p._p, anchor)

    def new_image_paras(block, anchor):
        """Returns the last inserted XML element, or None if it could not be built."""
        b64 = block.get("image_base64")
        if b64:
            if "," in b64[:100] and b64.strip().startswith("data:"):
                b64 = b64.split(",", 1)[1]
            data = base64.b64decode(b64)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            shape = p.add_run().add_picture(io.BytesIO(data))
            max_w = _content_width(doc)
            if shape.width > max_w:
                ratio = max_w / float(shape.width)
                shape.width = Emu(int(max_w))
                shape.height = Emu(int(shape.height * ratio))
            last = place(p._p, anchor)
            cap = _norm(block.get("caption"))
            if cap:
                last = caption_para(cap, last)
            return last

        # Existing image that was moved: clone its paragraph (+ caption).
        ii = _image_index(block)
        for oi, el in enumerate(original_elements):
            if _type(el) == "image" and _image_index(el) == ii and oi in main:
                last = place(copy.deepcopy(main[oi]), anchor)
                if oi in extra:
                    last = place(copy.deepcopy(extra[oi]), last)
                return last
        return None

    def delete_old(oi: int) -> bool:
        el = original_elements[oi]
        t = _type(el)
        x = main.get(oi)
        if x is None:
            return False
        if t == "image":
            if _norm(Paragraph(x, doc).text):
                # paragraph also holds text: drop only the picture runs
                for d in x.xpath(".//w:drawing | .//w:pict"):
                    d.getparent().remove(d)
            elif x.getparent() is not None:
                x.getparent().remove(x)
            cap = extra.get(oi)
            if cap is not None and cap.getparent() is not None:
                cap.getparent().remove(cap)
            removed.add(oi)
            return True
        if t in TEXT_TYPES and is_editable_text(oi):
            x.getparent().remove(x)
            removed.add(oi)
            return True
        return False  # tables are not deleted from the preview

    sm = difflib.SequenceMatcher(
        a=[_key(e, i, "a") for i, e in enumerate(original_elements)],
        b=[_key(e, i, "b") for i, e in enumerate(new_blocks)],
        autojunk=False,
    )

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        olds = list(range(i1, i2))
        news = list(range(j1, j2))

        # Anchor = last surviving original element before this change.
        anchor = None
        for oi in range(i1 - 1, -1, -1):
            if oi not in removed and last_xml(oi) is not None:
                anchor = last_xml(oi)
                break

        used_old: set = set()
        k_old = 0
        for nj in news:
            n = new_blocks[nj]
            nt = _type(n)

            # Pair a text block with the next unused editable old text paragraph.
            paired = None
            if nt in TEXT_TYPES:
                while k_old < len(olds) and not is_editable_text(olds[k_old]):
                    k_old += 1
                if k_old < len(olds):
                    paired = olds[k_old]
                    k_old += 1

            try:
                if paired is not None:
                    p = Paragraph(main[paired], doc)
                    if _norm(p.text) != _norm(_text(n)):
                        _set_paragraph_text(p, _text(n))
                        stats["edited"] += 1
                    used_old.add(paired)
                    anchor = last_xml(paired)
                elif nt in TEXT_TYPES:
                    anchor = new_text_para(n, anchor)
                    stats["inserted"] += 1
                elif nt == "image":
                    last = new_image_paras(n, anchor)
                    if last is None:
                        stats["skipped"] += 1
                    else:
                        anchor = last
                        stats["inserted"] += 1
                else:
                    stats["skipped"] += 1  # tables can't be created from the preview
            except Exception as exc:
                print(f"[block-editor] could not apply block {nj} ({nt}): {exc}")
                stats["skipped"] += 1

        for oi in olds:
            if oi in used_old:
                continue
            if _type(original_elements[oi]) == "table":
                continue  # leave tables alone
            if delete_old(oi):
                stats["deleted"] += 1
            else:
                stats["skipped"] += 1

    doc.save(docx_path)
    return stats


def docx_from_blocks(path: str, blocks: List[Dict[str, Any]]) -> None:
    """Fallback for non-DOCX sources (PDF/TXT): build a plain DOCX from blocks."""
    doc = Document()
    for b in blocks:
        t = _type(b)
        if t == "image":
            b64 = b.get("image_base64")
            if b64:
                try:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    shape = p.add_run().add_picture(io.BytesIO(base64.b64decode(b64)))
                    max_w = _content_width(doc)
                    if shape.width > max_w:
                        ratio = max_w / float(shape.width)
                        shape.width = Emu(int(max_w))
                        shape.height = Emu(int(shape.height * ratio))
                    if _norm(b.get("caption")):
                        doc.add_paragraph(_norm(b.get("caption")))
                except Exception as exc:
                    print(f"[block-editor] skip image: {exc}")
            continue
        if t not in TEXT_TYPES:
            continue
        text = _text(b)
        if t == "heading":
            lvl = b.get("level")
            lvl = lvl if isinstance(lvl, int) and 1 <= lvl <= 9 else 1
            doc.add_heading(text, level=lvl)
        elif t == "list_item":
            doc.add_paragraph(text, style="List Bullet")
        else:
            doc.add_paragraph(text)
    doc.save(path)
