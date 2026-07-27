"""Tests for blank interstitial page cleanup between cover/info."""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn

from docx_fields import (
    _is_page_break_only_paragraph,
    _paragraph_has_page_break,
    remove_blank_interstitial_pages,
)
from frontmatter_generator import _add_page_break, _strip_trailing_empty_paragraphs


def _page_break_only_count(doc: Document) -> int:
    return sum(
        1
        for p in doc.paragraphs
        if _is_page_break_only_paragraph(p._element)
    )


def test_add_page_break_attaches_to_content_not_new_para():
    doc = Document()
    doc.add_paragraph("Cover title")
    doc.add_paragraph("")  # trailing empty
    _add_page_break(doc)
    assert _page_break_only_count(doc) == 0, "must not create break-only paragraph"
    assert _paragraph_has_page_break(doc.paragraphs[0]._element) or any(
        _paragraph_has_page_break(p._element) for p in doc.paragraphs if p.text.strip()
    )
    print("PASS: _add_page_break attaches to content")


def test_absorb_break_only_removes_blank_page_artifact():
    doc = Document()
    doc.add_paragraph("COVER PAGE CONTENT")
    # Simulate old buggy merge: empty + dedicated page-break paragraph
    doc.add_paragraph("")
    br_para = doc.add_paragraph()
    br_para.add_run().add_break(WD_BREAK.PAGE)
    doc.add_paragraph("PROJECT DETAILS INFO PAGE")
    doc.add_paragraph("")
    br_para2 = doc.add_paragraph()
    br_para2.add_run().add_break(WD_BREAK.PAGE)
    doc.add_paragraph("Abstract body starts here")

    assert _page_break_only_count(doc) == 2
    stats = remove_blank_interstitial_pages(doc)
    assert stats["absorbed_breaks"] >= 2, stats
    assert _page_break_only_count(doc) == 0, "all break-only paras should be absorbed"
    texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    assert texts[0].startswith("COVER")
    assert any("PROJECT DETAILS" in t for t in texts)
    assert any("Abstract" in t for t in texts)
    # Content paragraphs still carry page breaks
    assert any(_paragraph_has_page_break(p._element) for p in doc.paragraphs)
    print("PASS: absorb break-only removes blank page artifact")


def test_merge_cover_info_no_break_only_paras():
    from frontmatter_generator import merge_frontmatter_into_report
    from io import BytesIO

    cover = Document()
    cover.add_paragraph("FORMATIFY COVER")
    cover.add_paragraph("")
    cbuf = BytesIO()
    cover.save(cbuf)

    info = Document()
    info.add_paragraph("Project Details")
    info.add_paragraph("Group members table goes here")
    ibuf = BytesIO()
    info.save(ibuf)

    body = Document()
    body.add_paragraph("Abstract")
    body.add_paragraph("Body paragraph")
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        body.save(tmp.name)
        path = tmp.name

    try:
        merged = merge_frontmatter_into_report(
            path,
            cover_bytes=cbuf.getvalue(),
            info_bytes=ibuf.getvalue(),
            insert_cover=True,
            insert_info=True,
        )
        out = Document(BytesIO(merged))
        assert _page_break_only_count(out) == 0, (
            f"merged doc still has {_page_break_only_count(out)} break-only paras"
        )
        plain = "\n".join(p.text for p in out.paragraphs)
        assert "FORMATIFY COVER" in plain
        assert "Project Details" in plain
        assert "Abstract" in plain
        print("PASS: merge_frontmatter produces no break-only blank pages")
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_add_page_break_attaches_to_content_not_new_para()
    test_absorb_break_only_removes_blank_page_artifact()
    test_merge_cover_info_no_break_only_paras()
    print("ALL PASS")
