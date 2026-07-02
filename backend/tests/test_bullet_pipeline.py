import tempfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from routers.documents import (
    _apply_bullets_to_paragraphs,
    _detect_bullet_groups_from_expanded_blocks,
    _detect_missing_bullet_issues,
)
from services.bullet_detection_service import BulletDetectionService
from services.bullet_sequence_detector import BulletSequenceDetector


def _has_ooxml_numbering(paragraph) -> bool:
    p_pr = paragraph._element.find(qn("w:pPr"))
    if p_pr is None:
        return False
    return p_pr.find(qn("w:numPr")) is not None


def test_section_group_detection_regression():
    blocks = [
        {"type": "heading", "text": "Methodology:"},
        {"type": "paragraph", "text": "• Gather the dataset"},
        {"type": "paragraph", "text": "2. Clean and normalize the dataset."},
        {"type": "paragraph", "text": "a) Train and evaluate the model"},
        {"type": "heading", "text": "Conclusion"},
    ]

    groups = _detect_bullet_groups_from_expanded_blocks(blocks)
    assert len(groups) == 1, f"expected one group, got: {groups}"
    assert [item["index"] for item in groups[0]] == [1, 2, 3]
    assert all(item["confidence"] >= 0.45 for item in groups[0])


def test_apply_bullets_adds_ooxml_and_strips_markers():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bullets.docx"
        doc = Document()

        heading = doc.add_paragraph("Methodology:")
        heading.style = "Heading 1"
        doc.add_paragraph("• Gather the dataset")
        doc.add_paragraph("2. Clean and normalize the dataset.")
        doc.add_paragraph("a) Train and evaluate the model")
        doc.save(path)

        _apply_bullets_to_paragraphs(str(path), [1, 2, 3], {})

        out_doc = Document(path)
        assert _has_ooxml_numbering(out_doc.paragraphs[1])
        assert _has_ooxml_numbering(out_doc.paragraphs[2])
        assert _has_ooxml_numbering(out_doc.paragraphs[3])

        assert not out_doc.paragraphs[1].text.startswith("•")
        assert not out_doc.paragraphs[2].text.startswith("2.")
        assert not out_doc.paragraphs[3].text.lower().startswith("a)")


def test_bullet_detection_service_groups_only_real_groups():
    service = BulletDetectionService()
    blocks = [
        {"type": "heading", "text": "Methodology"},
        {"type": "paragraph", "text": "• Gather data"},
        {"type": "paragraph", "text": "2. Clean data"},
        {
            "type": "paragraph",
            "text": (
                "This is a long prose paragraph that should not be treated as a list "
                "item because it reads like normal body text and has no marker."
            ),
        },
        {"type": "paragraph", "text": "a) Train model"},
    ]

    detected = service.detect_bullets_in_blocks(blocks)
    grouped = service.group_consecutive_bullets(detected)

    # At least one valid group with 2+ consecutive list-like items should exist.
    assert any(len(group) >= 2 for group in grouped), f"unexpected groups: {grouped}"


def test_detects_items_after_intro_colon_under_plain_heading():
    # Regression: headings like "TEST CASES" or "EXPECTED RESULTS" are often
    # followed by an intro sentence ending with ":" and then plain list lines.
    blocks = [
        {"type": "heading", "text": "TEST CASES"},
        {"type": "paragraph", "text": "The following scenarios were tested:"},
        {"type": "paragraph", "text": "Single-level list item detection"},
        {"type": "paragraph", "text": "Numbered-style semantic item detection"},
        {"type": "paragraph", "text": "Label-style list detection with colon prefixes"},
        {"type": "heading", "text": "EXPECTED RESULTS"},
        {"type": "paragraph", "text": "The formatter should:"},
        {"type": "paragraph", "text": "detect grouped list items correctly"},
        {"type": "paragraph", "text": "apply OOXML list formatting to detected groups"},
    ]

    groups = _detect_bullet_groups_from_expanded_blocks(blocks)
    flattened = [item["index"] for group in groups for item in group]

    # Must include list items after intro-colon lines in both sections.
    for expected in (2, 3, 4, 7, 8):
        assert expected in flattened, f"missing expected bullet index {expected}; got {flattened}"

    # Ensure they are grouped as actual list runs (not isolated single items).
    assert any(
        all(idx in [item["index"] for item in group] for idx in (2, 3, 4))
        for group in groups
    ), f"TEST CASES run was not grouped correctly: {groups}"


def test_colon_intro_fallback_works_without_heading_block():
    # No explicit heading before this list; detection should still work.
    blocks = [
        {"type": "paragraph", "text": "The following scenarios were tested:"},
        {"type": "paragraph", "text": "Single-level list item detection"},
        {"type": "paragraph", "text": "Numbered-style semantic item detection"},
        {"type": "paragraph", "text": "Label-style list detection with colon prefixes"},
        {"type": "paragraph", "text": "This paragraph is intentionally very long and descriptive and should stop list continuation because it behaves like regular prose instead of an item."},
    ]
    groups = _detect_bullet_groups_from_expanded_blocks(blocks)
    flattened = [item["index"] for group in groups for item in group]
    for expected in (1, 2, 3):
        assert expected in flattened, f"missing expected fallback index {expected}; groups={groups}"
    assert 4 not in flattened, f"long prose incorrectly included: {groups}"


def test_missing_bullet_issue_detector_avoids_long_prose_sections():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "proposal_like.docx"
        doc = Document()

        h = doc.add_paragraph("Objectives and Scope of the Project")
        h.style = "Heading 1"
        doc.add_paragraph(
            "The overall intent of the project is to build a complete AI-driven report "
            "formatter for institutions, integrating formatting templates, content "
            "classification, validation workflows, and quality checks over long-form text."
        )
        doc.add_paragraph(
            "The system scope includes backend APIs, frontend workflows, and model "
            "integration for document analysis and export, while remaining focused on "
            "maintainability, reliability, and policy compliance in academic contexts."
        )
        doc.add_paragraph(
            "It also includes usability improvements, section-level diagnostics, and "
            "consistent output generation across common submission formats."
        )
        doc.save(path)

        issues = _detect_missing_bullet_issues(str(path))
        assert issues == [] or all(
            issue.get("code") != "MISSING_BULLETS" for issue in issues
        ), f"long prose section incorrectly flagged as bullet issue: {issues}"


def test_sequence_detector_hybrid_grouping():
    detector = BulletSequenceDetector()
    blocks = [
        {"index": 0, "type": "heading", "text": "TEST CASES"},
        {"index": 1, "type": "paragraph", "text": "The following scenarios were tested:"},
        {"index": 2, "type": "paragraph", "text": "Single-level list item detection"},
        {"index": 3, "type": "paragraph", "text": "Numbered-style semantic item detection"},
        {"index": 4, "type": "paragraph", "text": "Label-style list detection with colon prefixes"},
        {"index": 5, "type": "paragraph", "text": "This is a deliberately long prose sentence that should stop list grouping because it is not a true list item and behaves like explanatory content."},
    ]
    groups = detector.detect_groups(blocks)
    flattened = [item["index"] for group in groups for item in group]
    assert 2 in flattened and 3 in flattened and 4 in flattened
    assert 5 not in flattened
