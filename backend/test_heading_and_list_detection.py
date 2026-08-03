"""Unit tests for heading Pass A/B classification and list detection pre-pass."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from heading_analysis import (
    AnalysisBlock,
    analyze_headings,
    find_missing_template_headings,
    build_template_outline,
    match_template_heading,
    MatchContext,
    _text_match_score,
)
from list_detection import (
    detect_list_groups,
    find_unconverted_parallel_runs,
    validate_list_coverage,
)


def _block(idx: int, text: str, **kwargs) -> AnalysisBlock:
    return AnalysisBlock(block_id=idx, text=text, paragraph_id=f"p{idx}", **kwargs)


TEMPLATE = {
    "required_sections": [
        {"name": "Introduction", "heading_level": 1},
        {"name": "Problem Statement", "heading_level": 2},
        {"name": "Main Objectives", "heading_level": 2},
        {"name": "Methodology", "heading_level": 1},
        {"name": "Conclusion", "heading_level": 1},
    ]
}


def test_soft_match_problem_to_problem_statement():
    score = _text_match_score("Problem", "Problem Statement")
    assert score >= 0.65, f"expected soft match, got {score}"
    matched, conf = match_template_heading(
        "Problem",
        build_template_outline(TEMPLATE["required_sections"]),
        MatchContext(),
    )
    assert matched == "Problem Statement"
    assert conf is not None and conf >= 0.65


def test_pass_a_matched_source():
    blocks = [
        _block(0, "1. Introduction", numbering_prefix="1"),
        _block(1, "This is body text under introduction that continues for a while."),
        _block(2, "Problem"),  # abbreviated form of Problem Statement
        _block(3, "Students struggle with academic formatting requirements daily."),
    ]
    results = analyze_headings(blocks, TEMPLATE)
    problem = results[2]
    assert problem["is_heading"] is True
    assert problem["source"] == "matched"
    assert problem["matched_template_heading"] == "Problem Statement"
    assert problem["level"] == "h2"


def test_pass_b_infers_specific_objectives():
    """'Specific Objectives' between a numbered heading and infinitive list."""
    blocks = [
        _block(0, "2.6 Main Objectives", numbering_prefix="2.6"),
        _block(1, "2.6.1 Main Goal", numbering_prefix="2.6.1"),
        _block(2, "Specific Objectives"),
        _block(3, "To develop a web-based formatting assistant for students."),
        _block(4, "To build an automated heading detection pipeline."),
        _block(5, "To implement list and bullet conversion reliably."),
    ]
    results = analyze_headings(blocks, TEMPLATE)

    main_goal = results[1]
    assert main_goal["is_heading"] is True
    assert main_goal["level"] == "h3"  # numbering depth 2.6.1 → 3

    specific = results[2]
    assert specific["is_heading"] is True, f"Specific Objectives not detected: {specific}"
    assert specific["source"] == "inferred"
    # Sibling of "2.6.1 Main Goal" (h3) under "2.6 Main Objectives" (h2)
    assert specific["level"] == "h3", f"expected h3 sibling level, got {specific['level']}"
    assert specific["heading_kind"] == "unnumbered_subheading"


def test_missing_template_heading():
    blocks = [
        _block(0, "1. Introduction", numbering_prefix="1"),
        _block(1, "Body under introduction with enough words to look like prose."),
        # No Problem Statement / Methodology / Conclusion
    ]
    results = analyze_headings(blocks, TEMPLATE, include_missing=False)
    outline = build_template_outline(TEMPLATE["required_sections"])
    missing = find_missing_template_headings(results, outline)
    names = {m["text"] for m in missing}
    assert "Problem Statement" in names
    assert "Methodology" in names
    assert "Conclusion" in names
    assert all(m["source"] == "missing" for m in missing)
    assert "Introduction" not in names


def test_list_infinitive_after_trigger():
    paras = [
        {"index": 0, "text": "The specific objectives of this project are:", "style": "Normal"},
        {"index": 1, "text": "To develop a robust document formatter for universities.", "style": "Normal"},
        {"index": 2, "text": "To build heading inference that works across templates.", "style": "Normal"},
        {"index": 3, "text": "To implement bullet detection for goal-style items.", "style": "Normal"},
        {"index": 4, "text": "3. Methodology", "style": "Heading 1", "type": "heading"},
    ]
    groups = detect_list_groups(paras)
    assert len(groups) >= 1
    g = groups[0]
    assert g.detection == "trigger_line"
    assert len(g.items) == 3
    assert all(i.text.startswith("To ") for i in g.items)


def test_list_label_colon_pattern():
    paras = [
        {"index": 0, "text": "Throughput: Handles 120 requests per second under load.", "style": "Normal"},
        {"index": 1, "text": "Latency: Average response time stays under 200ms.", "style": "Normal"},
        {"index": 2, "text": "Availability: Maintains 99.9 percent uptime yearly.", "style": "Normal"},
    ]
    groups = detect_list_groups(paras)
    assert len(groups) == 1
    assert groups[0].detection == "label_colon"
    assert len(groups[0].items) == 3


def test_list_parallel_infinitives_without_trigger():
    paras = [
        {"index": 0, "text": "To develop the core formatting engine.", "style": "Normal"},
        {"index": 1, "text": "To build a reliable heading classifier.", "style": "Normal"},
        {"index": 2, "text": "To implement list detection for all document types.", "style": "Normal"},
    ]
    groups = detect_list_groups(paras)
    assert len(groups) == 1
    assert groups[0].detection == "infinitive"


def test_aggregator_flags_unconverted_parallel_run():
    paras = [
        {"index": 0, "text": "To develop module A for parsing.", "style": "Normal"},
        {"index": 1, "text": "To build module B for batching.", "style": "Normal"},
        {"index": 2, "text": "To implement module C for dispatch.", "style": "Normal"},
        {"index": 3, "text": "To create module D for aggregation.", "style": "Normal"},
    ]
    # Simulate: nothing was converted
    flags = find_unconverted_parallel_runs(paras, min_run=3, treated_as_list_indices=[])
    assert len(flags) == 1
    assert flags[0]["pattern"] == "infinitive"
    assert flags[0]["count"] == 4
    assert flags[0]["source"] == "aggregator_list_validation"

    # After detection covers them, validation should be clean
    groups = detect_list_groups(paras)
    leftover = validate_list_coverage(paras, groups, min_run=3)
    assert leftover == []


def test_section_heading_never_listed():
    from list_detection import is_heading_paragraph, detect_list_groups
    assert is_heading_paragraph("3.2. Proposed Solution") is True
    assert is_heading_paragraph("• 3.2. Proposed Solution") is True
    paras = [
        {"index": 0, "text": "The features of the system are:", "style": "Normal"},
        {"index": 1, "text": "3.2. Proposed Solution", "style": "Normal"},
        {"index": 2, "text": "FORMATIFY works as a complete step-by-step tool.", "style": "Normal"},
    ]
    groups = detect_list_groups(paras)
    all_texts = [i.text for g in groups for i in g.items]
    assert "3.2. Proposed Solution" not in all_texts


def test_all_infinitives_one_group():
    paras = [
        {"index": i, "text": t, "style": "Normal"}
        for i, t in enumerate([
            "To develop an NLP-based content classification module using spaCy.",
            "To build an AI-powered Ethical Image Detection module for uploads.",
            "To introduce an Intelligent Image Formatting module for galleries.",
            "To develop a Voice-to-Command Interface for hands-free edits.",
            "To build a Version Control and Collaboration Module for groups.",
            "To develop a Mobile Companion Application with QR scanning.",
            "To build an Admin Panel that allows university administrators.",
        ])
    ]
    groups = detect_list_groups(paras)
    assert len(groups) == 1
    assert len(groups[0].items) == 7


def test_claude_first_matched_and_extra():
    """Claude candidates are seeded first; template match promotes; extras stay claude_only."""
    blocks = [
        _block(0, "1. Introduction", numbering_prefix="1"),
        _block(1, "Students often struggle with formatting long academic chapters carefully."),
        _block(2, "Custom Research Notes"),  # not in template
        _block(3, "Further discussion of findings continues across several paragraphs here."),
    ]
    claude = [
        {"paragraph_id": "p0", "level": 1, "confidence": 0.95},
        {"paragraph_id": "p2", "level": 2, "confidence": 0.9},
    ]
    results = analyze_headings(blocks, TEMPLATE, claude_candidates=claude)

    intro = results[0]
    assert intro["is_heading"] is True
    assert intro["source"] == "matched"
    assert intro["matched_template_heading"] == "Introduction"
    assert intro["user_decision"] == "keep"

    extra = results[2]
    assert extra["is_heading"] is True, f"extra not heading: {extra}"
    assert extra["source"] == "claude_only", f"expected claude_only, got {extra}"
    assert extra["user_decision"] == "pending"
    assert extra["matched_template_heading"] is None

    # Body paragraphs must not become headings
    assert results[1]["is_heading"] is False
    assert results[3]["is_heading"] is False


def test_claude_extra_discard_hides_heading():
    blocks = [
        _block(0, "Custom Research Notes"),
        _block(1, "Body text continuing after the custom notes heading."),
    ]
    claude = [{"paragraph_id": "p0", "level": 2, "confidence": 0.9}]
    results = analyze_headings(
        blocks,
        TEMPLATE,
        claude_candidates=claude,
        user_decisions={"p0": "discard"},
    )
    assert results[0]["source"] == "claude_only"
    assert results[0]["user_decision"] == "discard"
    assert results[0]["is_heading"] is False


def test_empty_template_zero_prefix_uses_claude_level():
    """No required_sections: '0.1 Abstract' must be H1 when Claude says so (not H2)."""
    empty = {"required_sections": []}
    blocks = [
        _block(0, "0.1. Abstract", numbering_prefix="0.1"),
        _block(1, "The offered project automates report formatting for students."),
        _block(2, "0.1.1 Admin Panel", numbering_prefix="0.1.1"),
        _block(3, "Admin panel details continue in this paragraph with enough words."),
    ]
    claude = [
        {"paragraph_id": "p0", "level": 1, "confidence": 0.95},
        {"paragraph_id": "p2", "level": 2, "confidence": 0.9},
    ]
    results = analyze_headings(blocks, empty, claude_candidates=claude)
    abstract = results[0]
    assert abstract["is_heading"] is True
    assert abstract["level"] == "h1", f"expected h1, got {abstract['level']}"
    assert abstract["source"] == "inferred"
    assert abstract["user_decision"] == "keep"
    sub = results[2]
    assert sub["is_heading"] is True
    assert sub["level"] == "h2", f"expected h2, got {sub['level']}"
    assert sub["user_decision"] == "keep"


def test_empty_template_zero_prefix_without_claude():
    """Reformatter path (no Claude): Abstract with 0.1 still becomes H1."""
    empty = {"required_sections": []}
    blocks = [
        _block(0, "0.1. Abstract", numbering_prefix="0.1"),
        _block(1, "The offered project automates report formatting for students carefully."),
    ]
    results = analyze_headings(blocks, empty)
    assert results[0]["is_heading"] is True
    assert results[0]["level"] == "h1", f"expected h1, got {results[0]['level']}"
    assert results[0]["user_decision"] == "keep"


def test_number_tracker_never_starts_at_zero():
    from reformatter import _HeadingNumberTracker

    t = _HeadingNumberTracker()
    # First heading wrongly treated as H2 must still start at 1.1, not 0.1
    assert t.next_number(2) == "1.1"
    assert t.next_number(1) == "2"
    assert t.next_number(2) == "2.1"


def test_renumber_heading_prefixes_strips_zero():
    import tempfile
    from docx import Document as DocxDoc
    from content_fixer import renumber_heading_prefixes

    doc = DocxDoc()
    p0 = doc.add_paragraph("0.1. Abstract")
    p0.style = doc.styles["Heading 1"]
    p1 = doc.add_paragraph("0.1.1 Scope")
    p1.style = doc.styles["Heading 2"]
    p2 = doc.add_paragraph("Introduction body text.")
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        path = tmp.name
    doc.save(path)
    try:
        n = renumber_heading_prefixes(path)
        assert n >= 1
        out = DocxDoc(path)
        assert out.paragraphs[0].text.startswith("1."), out.paragraphs[0].text
        assert "Abstract" in out.paragraphs[0].text
        assert out.paragraphs[1].text.startswith("1.1."), out.paragraphs[1].text
        assert "Scope" in out.paragraphs[1].text
    finally:
        os.unlink(path)


if __name__ == "__main__":
    tests = [
        test_soft_match_problem_to_problem_statement,
        test_pass_a_matched_source,
        test_pass_b_infers_specific_objectives,
        test_missing_template_heading,
        test_list_infinitive_after_trigger,
        test_list_label_colon_pattern,
        test_list_parallel_infinitives_without_trigger,
        test_aggregator_flags_unconverted_parallel_run,
        test_section_heading_never_listed,
        test_all_infinitives_one_group,
        test_claude_first_matched_and_extra,
        test_claude_extra_discard_hides_heading,
        test_empty_template_zero_prefix_uses_claude_level,
        test_empty_template_zero_prefix_without_claude,
        test_number_tracker_never_starts_at_zero,
        test_renumber_heading_prefixes_strips_zero,
    ]

    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(failed)
