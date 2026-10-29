"""LOF/LOT must skip cover+info; no LOT without body tables; sequential numbers."""

from __future__ import annotations

import io
import os
import tempfile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from PIL import Image

from docx_tools.docx_fields import (
    FORMATIFY_BODY_START_BOOKMARK,
    analyze_document_lists,
    generate_document_lists,
    paragraph_has_image,
    paragraph_is_figure_caption,
)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (20, 80, 160)).save(buf, format="PNG")
    return buf.getvalue()


def _add_png(paragraph) -> None:
    run = paragraph.add_run()
    run.add_picture(io.BytesIO(_png_bytes()), width=Inches(0.4))


def _page_break(doc) -> None:
    p = doc.add_paragraph()
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    r.append(br)
    p._element.append(r)


def _place_body_start_on(para) -> None:
    """Put Formatify body-start bookmark on the given paragraph."""
    p_el = para._element
    # Remove any existing body-start bookmarks
    for bm in list(para.part.element.body.iter(qn("w:bookmarkStart"))):
        if bm.get(qn("w:name")) == FORMATIFY_BODY_START_BOOKMARK:
            bm_id = bm.get(qn("w:id"))
            parent = bm.getparent()
            if parent is not None:
                parent.remove(bm)
            for end in list(para.part.element.body.iter(qn("w:bookmarkEnd"))):
                if end.get(qn("w:id")) == bm_id:
                    ep = end.getparent()
                    if ep is not None:
                        ep.remove(end)
    bm_start = OxmlElement("w:bookmarkStart")
    bm_start.set(qn("w:id"), "9001")
    bm_start.set(qn("w:name"), FORMATIFY_BODY_START_BOOKMARK)
    bm_end = OxmlElement("w:bookmarkEnd")
    bm_end.set(qn("w:id"), "9001")
    p_el.insert(0, bm_start)
    p_el.append(bm_end)


def _build_fixture() -> str:
    doc = Document()

    # Cover page with logo
    cover = doc.add_paragraph()
    _add_png(cover)
    doc.add_paragraph("COMSATS University")
    _page_break(doc)

    # Project details page with a form table (NOT a report table)
    doc.add_paragraph("Project Details")
    info_table = doc.add_table(rows=2, cols=2)
    info_table.rows[0].cells[0].text = "Project ID (for office use)"
    info_table.rows[0].cells[1].text = ""
    info_table.rows[1].cells[0].text = "Supervisor"
    info_table.rows[1].cells[1].text = "Dr. X"
    _page_break(doc)

    # Report body
    body_h = doc.add_paragraph("1 Introduction")
    body_h.style = "Heading 1"
    _place_body_start_on(body_h)
    doc.add_paragraph("Body text about the project.")

    for _ in range(2):
        img_p = doc.add_paragraph()
        _add_png(img_p)

    methods = doc.add_paragraph("2 Methods")
    methods.style = "Heading 1"
    doc.add_paragraph("More body text.")

    path = os.path.join(tempfile.gettempdir(), "formatify_lof_lot_frontmatter.docx")
    doc.save(path)
    return path


def main() -> None:
    path = _build_fixture()
    result = generate_document_lists(
        path,
        {},
        [],
        include_toc=True,
        include_lot=True,
        include_lof=True,
    )

    d = Document(path)
    status = analyze_document_lists(d)
    texts = [p.text.strip() for p in d.paragraphs if p.text.strip()]

    # No body tables → no LOT
    assert status["table_count"] == 0, status
    assert not result.get("lot_added"), result
    assert not status["has_lot"], status
    assert not any(t.lower() == "list of tables" for t in texts), texts

    # LOF present; body figures only
    assert result.get("lof_added"), result
    assert status["figure_count"] == 2, status

    figure_lines = [t for t in texts if t.startswith("Figure ")]
    assert any(t.startswith("Figure 1:") for t in figure_lines), figure_lines
    assert any(t.startswith("Figure 2:") for t in figure_lines), figure_lines

    # No raw LOF/LOT field instruction text
    joined = "\n".join(texts)
    assert 'TOC \\h \\z \\c "Figure"' not in joined, joined
    assert 'TOC \\h \\z \\c "Table"' not in joined, joined

    # Cover logo must not have a figure caption under it
    for i, para in enumerate(d.paragraphs):
        if not paragraph_has_image(para):
            continue
        nearby = " ".join(
            (d.paragraphs[j].text or "")
            for j in range(max(0, i - 1), min(len(d.paragraphs), i + 3))
        )
        if "COMSATS" in nearby:
            if i + 1 < len(d.paragraphs):
                assert not paragraph_is_figure_caption(d.paragraphs[i + 1]), d.paragraphs[i + 1].text
            break

    print("ALL ASSERTIONS PASSED")
    print(
        {
            k: result.get(k)
            for k in (
                "lof_added",
                "lot_added",
                "toc_added",
                "figure_count",
                "table_count",
            )
        }
    )


if __name__ == "__main__":
    main()
