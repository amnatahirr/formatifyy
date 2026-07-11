"""Quick smoke test for TOC / LOT / LOF generation."""

from __future__ import annotations

import os
import tempfile

from docx import Document

from docx_fields import (
    _paragraph_has_page_break,
    analyze_document_lists,
    generate_document_lists,
)
from docx_styles import force_heading_style
from table_processor import detect_tables


def main() -> None:
    doc = Document()
    h = doc.add_paragraph("Table of Contents")
    force_heading_style(h, doc, 1)

    p1 = doc.add_paragraph("Introduction")
    force_heading_style(p1, doc, 1)
    p2 = doc.add_paragraph("Background")
    force_heading_style(p2, doc, 2)
    doc.add_paragraph("Some intro text.")
    p3 = doc.add_paragraph("Methodology")
    force_heading_style(p3, doc, 1)
    doc.add_paragraph("Methods description.")

    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "Column A"
    table.rows[0].cells[1].text = "Column B"
    table.rows[1].cells[0].text = "1"
    table.rows[1].cells[1].text = "2"

    lot_h = doc.add_paragraph("List of Tables")
    force_heading_style(lot_h, doc, 1)
    lof_h = doc.add_paragraph("List of Figures")
    force_heading_style(lof_h, doc, 1)

    path = os.path.join(tempfile.gettempdir(), "formatify_test_lists.docx")
    doc.save(path)
    print(f"Created: {path}")

    result = generate_document_lists(path, {}, [])
    print("generate:", {k: result[k] for k in (
        "toc_added", "lot_added", "lof_added", "entry_count", "table_captions_added",
    ) if k in result})

    d2 = Document(path)
    status = analyze_document_lists(d2)
    print("status:", {k: status[k] for k in (
        "has_toc", "has_lot", "has_lof", "heading_count", "table_count",
    )})
    print("headings:", [h["text"] for h in status["headings"]])
    print("tables detected:", len(detect_tables(d2)))

    front_matter = []
    for para in d2.paragraphs[:12]:
        text = para.text.strip()
        if text:
            front_matter.append(text)
        if _paragraph_has_page_break(para._element):
            front_matter.append("[PAGE BREAK]")
    print("front matter:", front_matter)
    assert front_matter[0].lower().startswith("table of contents"), "TOC must be first"
    assert any("list of tables" in item.lower() for item in front_matter), "LOT missing"
    assert "[PAGE BREAK]" in front_matter, "Expected page breaks between front-matter sections"

    assert status["has_toc"], "TOC field missing"
    assert status["has_lot"], "LOT field missing"
    assert status["table_count"] == 1
    print("ALL ASSERTIONS PASSED")

    # TOC-only run: orphan LOF/LOT headings must not reserve extra pages.
    doc2 = Document()
    doc2.add_paragraph("Table of Contents").style = "Heading 1"
    doc2.add_paragraph("Introduction").style = "Heading 1"
    doc2.add_paragraph("Some intro text.")
    doc2.add_paragraph("List of Tables").style = "Heading 1"
    doc2.add_paragraph("List of Figures").style = "Heading 1"
    path2 = os.path.join(tempfile.gettempdir(), "formatify_test_toc_only.docx")
    doc2.save(path2)
    generate_document_lists(
        path2,
        {},
        [],
        include_toc=True,
        include_lot=False,
        include_lof=False,
    )
    d3 = Document(path2)
    texts = [p.text.strip().lower() for p in d3.paragraphs if p.text.strip()]
    assert not any("list of tables" in t for t in texts), "LOT heading should be removed"
    assert not any("list of figures" in t for t in texts), "LOF heading should be removed"
    page_breaks = sum(1 for p in d3.paragraphs if _paragraph_has_page_break(p._element))
    assert page_breaks == 1, f"Expected one page break before content, got {page_breaks}"
    print("TOC-only edge-case assertions passed")


if __name__ == "__main__":
    main()
