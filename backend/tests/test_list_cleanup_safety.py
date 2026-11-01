"""Regression: list-field cleanup must never wipe the report body."""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from docx.enum.text import WD_BREAK

from docx_tools.docx_fields import (
    _build_toc_field_end_paragraph,
    _build_toc_field_start_paragraph,
    _cleanup_all_list_artifacts,
    _paragraph_is_visually_empty,
    _remove_list_field_block,
    LOF_FIELD_RE,
    remove_blank_interstitial_pages,
    insert_lof_field,
)


def test_field_end_not_visually_empty():
    end = _build_toc_field_end_paragraph()
    assert not _paragraph_is_visually_empty(end), "field end must be preserved"
    start = _build_toc_field_start_paragraph('TOC \\h \\z \\c "Figure"')
    assert not _paragraph_is_visually_empty(start)
    print("PASS: field markers are not visually empty")


def test_blank_cleanup_preserves_field_end():
    doc = Document()
    doc.add_paragraph("List of Figures")
    doc.element.body.append(_build_toc_field_start_paragraph('TOC \\h \\z \\c "Figure"'))
    doc.add_paragraph("Figure 1: Demo")
    doc.element.body.append(_build_toc_field_end_paragraph())
    # Trailing page-break-only (old merge artifact)
    br = doc.add_paragraph()
    br.add_run().add_break(WD_BREAK.PAGE)
    doc.add_paragraph("Introduction body content that must survive cleanup.")

    before = len(doc.paragraphs)
    remove_blank_interstitial_pages(doc)
    texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    assert any("Introduction body" in t for t in texts), texts
    assert any("List of Figures" in t for t in texts), texts
    # Field end still present
    from docx.oxml.ns import qn
    ends = [
        p
        for p in doc.paragraphs
        if any(br.get(qn("w:fldCharType")) == "end" for br in p._element.iter(qn("w:fldChar")))
        and not any(br.get(qn("w:fldCharType")) == "begin" for br in p._element.iter(qn("w:fldChar")))
    ]
    assert ends, "field end paragraph was deleted by blank cleanup"
    assert len(doc.paragraphs) >= before - 3
    print("PASS: blank cleanup preserves field end + body")


def test_remove_list_field_without_end_does_not_wipe_body():
    doc = Document()
    doc.add_paragraph("Cover page title")
    doc.add_paragraph("List of Figures")
    # Field start but NO end marker (simulates blank-cleanup damage)
    doc.element.body.append(_build_toc_field_start_paragraph('TOC \\h \\z \\c "Figure"'))
    # fake entry-ish short line
    doc.add_paragraph("Figure 1: Seal")
    # Body that old bug deleted
    for i in range(40):
        doc.add_paragraph(
            f"Chapter paragraph {i}: This is substantial report body content "
            f"that must never be deleted by list field cleanup routines."
        )

    before = len([p for p in doc.paragraphs if "Chapter paragraph" in (p.text or "")])
    assert before == 40
    _remove_list_field_block(doc, LOF_FIELD_RE)
    after = len([p for p in doc.paragraphs if "Chapter paragraph" in (p.text or "")])
    assert after == 40, f"body wiped: {before} -> {after}"
    assert any("Cover page" in (p.text or "") for p in doc.paragraphs)
    print("PASS: remove_list_field without end keeps body")


def test_cleanup_all_then_regenerate_keeps_body():
    doc = Document()
    doc.add_paragraph("FORMATIFY Cover")
    doc.add_paragraph("Project Details info page")
    for i in range(20):
        doc.add_paragraph(
            f"Body section {i}. Detailed academic writing for the FYP mid report "
            f"with enough length to look like real content for the safety guard."
        )
    # Insert a proper LOF then strip its end (damage), then cleanup
    insert_lof_field(doc, entries=[{
        "level": 1,
        "text": "Figure 1: Demo",
        "bookmark": "_Toc000000001",
    }])
    # Delete end markers artificially
    from docx.oxml.ns import qn
    for p in list(doc.paragraphs):
        chars = list(p._element.iter(qn("w:fldChar")))
        types = [c.get(qn("w:fldCharType")) for c in chars]
        if types == ["end"]:
            p._element.getparent().remove(p._element)

    body_before = len([p for p in doc.paragraphs if "Body section" in (p.text or "")])
    _cleanup_all_list_artifacts(doc)
    body_after = len([p for p in doc.paragraphs if "Body section" in (p.text or "")])
    assert body_after == body_before, f"cleanup wiped body {body_before}->{body_after}"
    print("PASS: cleanup_all with missing end keeps body")


if __name__ == "__main__":
    test_field_end_not_visually_empty()
    test_blank_cleanup_preserves_field_end()
    test_remove_list_field_without_end_does_not_wipe_body()
    test_cleanup_all_then_regenerate_keeps_body()
    print("ALL PASS")
