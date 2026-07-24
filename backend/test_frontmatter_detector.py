"""Unit tests for frontmatter cover / info page heuristic detection.

Creates five mock DOCX samples:
  1. both cover + info present
  2. missing cover only
  3. missing info page only
  4. missing both
  5. unusual / edge-case layout
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Pt

from frontmatter_detector import (
    detect_frontmatter_heuristic,
    extract_first_pages,
)


def _page_break(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run()
    run.add_break(WD_BREAK.PAGE)


def _centered(doc: Document, text: str, size: int = 14, bold: bool = False) -> None:
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.bold = bold
        run.font.size = Pt(size)


def _build_cover(doc: Document) -> None:
    _centered(doc, "COMSATS University Islamabad", size=16, bold=True)
    _centered(doc, "Department of Computer Science", size=12)
    _centered(doc, "Formatify: AI Document Formatter", size=20, bold=True)
    _centered(doc, "Final Year Project Report", size=14)
    _centered(doc, "Submitted in partial fulfilment of the BS degree", size=11)
    _centered(doc, "Session: Fall 2025", size=11)


def _build_info(doc: Document) -> None:
    doc.add_paragraph("Project Details")
    doc.add_paragraph("Project Title: Formatify AI Document Formatter")
    doc.add_paragraph("Group Members:")
    doc.add_paragraph("Ali Khan | Reg No: CIIT/FA21-BCS-001")
    doc.add_paragraph("Sara Ahmed | Reg No: CIIT/FA21-BCS-014")
    doc.add_paragraph("Supervisor: Dr. Example Supervisor")
    doc.add_paragraph("Co-Supervisor: —")
    doc.add_paragraph("Domain: ☐ AI  ☑ NLP  ☐ Mobile  ☐ Web")
    table = doc.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Student Name"
    table.cell(0, 1).text = "Registration No"
    table.cell(1, 0).text = "Ali Khan"
    table.cell(1, 1).text = "CIIT/FA21-BCS-001"
    table.cell(2, 0).text = "Sara Ahmed"
    table.cell(2, 1).text = "CIIT/FA21-BCS-014"


def _build_body_chapter(doc: Document, title: str = "1. Introduction") -> None:
    doc.add_paragraph(title)
    doc.add_paragraph(
        "This chapter introduces the problem domain and motivation for the project. "
        "Academic report formatting is tedious and error-prone for students who must "
        "comply with university templates covering headings, margins, captions, and "
        "references. The following sections describe the background, objectives, and "
        "scope of the proposed system in detail with substantial body prose that is "
        "clearly not a cover page or a project details sheet."
    )
    doc.add_paragraph(
        "Furthermore, related tools only address fragments of the pipeline and do not "
        "combine structural analysis with vision-based image checks. Our approach aims "
        "to unify these concerns into a single student-facing workflow."
    )


def _save(doc: Document, folder: str, name: str) -> str:
    path = os.path.join(folder, name)
    doc.save(path)
    return path


def _make_both(folder: str) -> str:
    doc = Document()
    _build_cover(doc)
    _page_break(doc)
    _build_info(doc)
    _page_break(doc)
    _build_body_chapter(doc)
    return _save(doc, folder, "both.docx")


def _make_missing_cover(folder: str) -> str:
    """Page 1 = chapter body (no cover); page 2 = project details."""
    doc = Document()
    _build_body_chapter(doc)
    _page_break(doc)
    _build_info(doc)
    return _save(doc, folder, "missing_cover.docx")


def _make_missing_info(folder: str) -> str:
    doc = Document()
    _build_cover(doc)
    _page_break(doc)
    _build_body_chapter(doc, title="1. Introduction")
    return _save(doc, folder, "missing_info.docx")


def _make_missing_both(folder: str) -> str:
    doc = Document()
    _build_body_chapter(doc, title="1. Introduction")
    _page_break(doc)
    _build_body_chapter(doc, title="2. Literature Review")
    return _save(doc, folder, "missing_both.docx")


def _make_unusual(folder: str) -> str:
    """Edge case: large centered title + dense prose, no institution branding."""
    doc = Document()
    _centered(doc, "My Cool Project Title That Is Quite Long", size=18, bold=True)
    doc.add_paragraph(
        "Although the title is centered and large, the rest of page one is a long "
        "narrative abstract that continues for many sentences without naming any "
        "institution, advisor, or emblem. This should look ambiguous or non-cover "
        "to a strict heuristic because body density dominates the layout signals."
    )
    doc.add_paragraph(
        "Additional abstract sentences reinforce that this is not a traditional "
        "branded title sheet used for formal student project submissions."
    )
    _page_break(doc)
    doc.add_paragraph("2. Background")
    doc.add_paragraph(
        "Somewhere in the chapter we casually mention advisor feedback and "
        "enrollment processes without a structured table or key-value block."
    )
    return _save(doc, folder, "unusual.docx")


def test_both_pages_present():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_both(tmp)
        result, _ = detect_frontmatter_heuristic(path)
        assert result.cover_page_present is True, result.reasoning
        assert result.info_page_present is True, result.reasoning
        assert result.cover_confidence >= 0.55
        assert result.info_confidence >= 0.55


def test_missing_cover_only():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_missing_cover(tmp)
        result, _ = detect_frontmatter_heuristic(path)
        assert result.cover_page_present is False, result.reasoning
        assert result.info_page_present is True, result.reasoning


def test_missing_info_only():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_missing_info(tmp)
        result, _ = detect_frontmatter_heuristic(path)
        assert result.cover_page_present is True, result.reasoning
        assert result.info_page_present is False, result.reasoning


def test_missing_both():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_missing_both(tmp)
        result, _ = detect_frontmatter_heuristic(path)
        assert result.cover_page_present is False, result.reasoning
        assert result.info_page_present is False, result.reasoning


def test_unusual_layout_edge_case():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_unusual(tmp)
        result, pages = detect_frontmatter_heuristic(path)
        # Should not confidently claim a proper university cover + structured info page
        assert not (
            result.cover_page_present and result.cover_confidence >= 0.85
        ), f"unusual layout should not be a high-confidence cover: {result.reasoning}"
        assert result.info_page_present is False, result.reasoning
        # Soft split / page extraction still returns two pages
        assert len(pages) == 2


def test_extract_first_pages_returns_two():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_both(tmp)
        pages = extract_first_pages(path, max_pages=2)
        assert len(pages) == 2
        assert pages[0].page_number == 1
        assert any("COMSATS" in p.text for p in pages[0].paragraphs)


if __name__ == "__main__":
    tests = [
        test_both_pages_present,
        test_missing_cover_only,
        test_missing_info_only,
        test_missing_both,
        test_unusual_layout_edge_case,
        test_extract_first_pages_returns_two,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {fn.__name__}: {exc}")
    if failed:
        print(f"\n{failed}/{len(tests)} failed")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed.")
