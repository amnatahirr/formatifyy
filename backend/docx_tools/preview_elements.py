import os
from docx import Document as DocxDoc
from docx.table import Table
from docx.text.paragraph import Paragraph

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_ALIGN = {0: "left", 1: "center", 2: "right", 3: "justify"}


def _para_images(p, doc, doc_id, images_dir, counter):
    """Save images embedded in paragraph p; return list of relative paths."""
    out = []
    for blip in p._p.iter(_A + "blip"):
        rid = blip.get(_R + "embed")
        if not rid or rid not in doc.part.related_parts:
            continue
        part = doc.part.related_parts[rid]
        ext = os.path.splitext(part.partname)[1] or ".png"
        os.makedirs(images_dir, exist_ok=True)
        name = f"pimg{counter[0]}{ext}"
        counter[0] += 1
        with open(os.path.join(images_dir, name), "wb") as f:
            f.write(part.blob)
        out.append(f"images/doc_{doc_id}/{name}")
    return out


def _has_page_break(p):
    return any(
        br.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type") == "page"
        for br in p._p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br")
    ) or bool(list(p._p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lastRenderedPageBreak")))


def _run_fmt(p):
    runs = [r for r in p.runs if r.text.strip()]
    if not runs:
        return {}
    f = {}
    if all(r.bold for r in runs):
        f["bold"] = True
    if all(r.italic for r in runs):
        f["italic"] = True
    if all(r.underline for r in runs):
        f["underline"] = True
    r0 = runs[0]
    if r0.font.name:
        f["font_name"] = r0.font.name
    if r0.font.size:
        f["font_size"] = r0.font.size.pt
    return f


def build_preview_elements(file_path, document_id, images_dir):
    """Body-order walk: paragraphs, headings, list items, images, tables."""
    doc = DocxDoc(file_path)
    elements, counter, page = [], [0], 1
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            if _has_page_break(p):
                page += 1
            for rel in _para_images(p, doc, document_id, images_dir, counter):
                elements.append({"type": "image", "text": "", "image_path": rel,
                                 "image_index": counter[0] - 1, "page": page, "caption": ""})
            text = p.text.strip()
            if not text:
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            el = {"text": p.text, "page": page}
            if "heading" in style or style == "title":
                el["type"] = "heading"
                digits = [c for c in style if c.isdigit()]
                el["level"] = int(digits[0]) if digits else 1
            elif "list" in style or child.find(
                    ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr") is not None:
                el["type"] = "list_item"
                el["list_style"] = "number" if "number" in style else "bullet"
            else:
                el["type"] = "paragraph"
            if p.alignment is not None:
                el["alignment"] = _ALIGN.get(int(p.alignment), "left")
            el.update(_run_fmt(p))
            # a caption line right after an image becomes its caption
            if elements and elements[-1]["type"] == "image" and text.lower().startswith(("figure", "fig.")):
                elements[-1]["caption"] = text
                elements[-1]["text"] = text
                continue
            elements.append(el)
        elif tag == "tbl":
            t = Table(child, doc)
            rows = []
            for r in t.rows:
                seen, cells = set(), []
                for c in r.cells:
                    if id(c._tc) in seen:  # merged cells repeat
                        continue
                    seen.add(id(c._tc))
                    cells.append(c.text.strip())
                rows.append(cells)
            elements.append({"type": "table", "text": "", "rows": rows, "page": page})
    return elements