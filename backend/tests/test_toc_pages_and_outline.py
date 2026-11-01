"""TOC title unnumbered; page refs vary; body outline numbers stripped."""

from __future__ import annotations

import io
import os
import tempfile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from PIL import Image

from docx_tools.docx_fields import (
    FORMATIFY_BODY_START_BOOKMARK,
    generate_document_lists,
    _is_valid_toc_source_heading,
)


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (10, 100, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _page_break(doc) -> None:
    p = doc.add_paragraph()
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    r.append(br)
    p._element.append(r)


def _body_bookmark(para) -> None:
    p_el = para._element
    bm_start = OxmlElement("w:bookmarkStart")
    bm_start.set(qn("w:id"), "9100")
    bm_start.set(qn("w:name"), FORMATIFY_BODY_START_BOOKMARK)
    bm_end = OxmlElement("w:bookmarkEnd")
    bm_end.set(qn("w:id"), "9100")
    p_el.insert(0, bm_start)
    p_el.append(bm_end)


def _add_outline_numpr(para, num_id: str = "1") -> None:
    p_pr = para._element.get_or_add_pPr()
    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    nid = OxmlElement("w:numId")
    nid.set(qn("w:val"), num_id)
    num_pr.extend([ilvl, nid])
    p_pr.insert(0, num_pr)


def main() -> None:
    assert not _is_valid_toc_source_heading(
        "The specific objectives of the project are"
    )
    assert _is_valid_toc_source_heading("Objectives and Scope of the Project")

    doc = Document()
    doc.add_paragraph("Cover Uni")
    _page_break(doc)
    doc.add_paragraph("Project Details")
    _page_break(doc)

    toc = doc.add_paragraph("5. Table of Contents")
    toc.style = "Heading 1"
    _add_outline_numpr(toc)

    intro = doc.add_paragraph("1 Introduction")
    intro.style = "Heading 1"
    _body_bookmark(intro)

    # Long body prose wrongly carrying outline number + numPr
    body = doc.add_paragraph(
        "6. The processing module analyses audio signals and converts them "
        "into structured commands for the downstream control pipeline."
    )
    _add_outline_numpr(body)

    false_h = doc.add_paragraph("The specific objectives of the project are")
    false_h.style = "Heading 1"

    methods = doc.add_paragraph("Methods")
    methods.style = "Heading 1"
    doc.add_paragraph("Method details go here with enough text to pad content. " * 80)
    _page_break(doc)
    doc.add_paragraph("Results").style = "Heading 1"
    doc.add_paragraph("Results content continues on a later page. " * 80)

    img = doc.add_paragraph()
    img.add_run().add_picture(io.BytesIO(_png()), width=Inches(1.0))

    path = os.path.join(tempfile.gettempdir(), "formatify_toc_pages_fix.docx")
    doc.save(path)

    result = generate_document_lists(
        path, {"heading1_size": 16}, [], include_toc=True, include_lof=True, include_lot=False
    )
    assert result.get("toc_added"), result

    d = Document(path)
    texts = [p.text.strip() for p in d.paragraphs if p.text.strip()]

    # TOC title must not keep "5."
    toc_titles = [t for t in texts if "table of contents" in t.lower()]
    assert toc_titles, texts
    assert not any(t.lower().startswith("5.") for t in toc_titles), toc_titles
    assert any(t.lower() == "table of contents" for t in toc_titles), toc_titles

    # False heading sentence must not appear as a TOC entry (tab + page)
    toc_entry_texts = []
    for p in d.paragraphs:
        plain = "".join(t.text or "" for t in p._element.iter(qn("w:t")))
        if any("PAGEREF" in (i.text or "") for i in p._element.iter(qn("w:instrText"))):
            toc_entry_texts.append(plain)
    assert not any(
        "specific objectives of the project are" in t.lower() for t in toc_entry_texts
    ), toc_entry_texts

    # Body prose must not keep leading "6."
    joined = "\n".join(texts)
    assert "6. The processing module" not in joined, joined
    assert "processing module analyses audio" in joined.lower()

    # TOC page numbers should not all be 1 when content spans pages
    toc_pages = []
    for p in d.paragraphs:
        has_pageref = any(
            "PAGEREF" in (instr.text or "")
            for instr in p._element.iter(qn("w:instrText"))
        )
        if not has_pageref:
            continue
        # Field result is the last w:t in the paragraph
        texts_xml = [t.text or "" for t in p._element.iter(qn("w:t"))]
        if texts_xml and texts_xml[-1].strip().isdigit():
            toc_pages.append(int(texts_xml[-1].strip()))
    assert toc_pages, "No PAGEREF pages found"
    assert max(toc_pages) >= 2, f"Expected varied pages, got {toc_pages}"

    print("ALL ASSERTIONS PASSED")
    print({"toc_pages": toc_pages, "toc_titles": toc_titles})


if __name__ == "__main__":
    main()
