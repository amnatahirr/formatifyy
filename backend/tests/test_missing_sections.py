"""
Tests for missing_sections.py - build_previews() function.

Covers edge cases:
- One missing section
- Two adjacent missing sections
- Missing at end of document
- None missing
"""
import pytest


def test_build_previews_one_missing():
    """Test build_previews with a single missing section."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [
            {
                "name": "Abstract",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": 5,
            }
        ],
    }

    previews = build_previews(info)

    assert len(previews) == 1
    assert previews[0]["issue_id"] == "missing_heading_abstract"
    assert previews[0]["is_placeholder"] is True
    assert previews[0]["name"] == "Abstract"
    assert previews[0]["level"] == 1
    assert previews[0]["optional"] is False
    assert previews[0]["insert_before_paragraph_index"] == 5
    assert previews[0]["insert_before_paragraph_id"] == "p5"
    assert previews[0]["insert_after_paragraph_index"] == 4
    assert previews[0]["insert_after_paragraph_id"] == "p4"
    assert previews[0]["position"] == "before"
    assert "placeholder_text" in previews[0]
    assert "guidance_text" in previews[0]
    assert previews[0]["suggested_content"] is None


def test_build_previews_two_adjacent_missing():
    """Test build_previews with two adjacent missing sections (same insert_before)."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [
            {
                "name": "Abstract",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": 5,
            },
            {
                "name": "Introduction",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": 5,  # Same as Abstract
            }
        ],
    }

    previews = build_previews(info)

    assert len(previews) == 2
    
    # First missing section
    assert previews[0]["issue_id"] == "missing_heading_abstract"
    assert previews[0]["name"] == "Abstract"
    assert previews[0]["insert_before_paragraph_index"] == 5
    assert previews[0]["insert_before_paragraph_id"] == "p5"
    assert previews[0]["insert_after_paragraph_index"] == 4
    assert previews[0]["insert_after_paragraph_id"] == "p4"
    
    # Second missing section (adjacent, same insertion point)
    assert previews[1]["issue_id"] == "missing_heading_introduction"
    assert previews[1]["name"] == "Introduction"
    assert previews[1]["insert_before_paragraph_index"] == 5
    assert previews[1]["insert_before_paragraph_id"] == "p5"
    # Both should insert after the same paragraph (p4)
    assert previews[1]["insert_after_paragraph_index"] == 4
    assert previews[1]["insert_after_paragraph_id"] == "p4"


def test_build_previews_missing_at_end():
    """Test build_previews with a missing section at the end of document."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [
            {
                "name": "References",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": None,  # End of document
            }
        ],
        "found": [
            {
                "name": "Conclusion",
                "paragraph_index": 20,
            }
        ],
    }

    previews = build_previews(info)

    assert len(previews) == 1
    assert previews[0]["issue_id"] == "missing_heading_references"
    assert previews[0]["name"] == "References"
    assert previews[0]["insert_before_paragraph_index"] is None
    assert previews[0]["insert_before_paragraph_id"] is None
    assert previews[0]["insert_after_paragraph_index"] == 20  # After last found section
    assert previews[0]["insert_after_paragraph_id"] == "p20"
    assert previews[0]["position"] == "end"


def test_build_previews_missing_at_end_no_found():
    """Test build_previews with missing at end when no sections exist at all."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [
            {
                "name": "Abstract",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": None,
            }
        ],
        "found": [],  # No existing sections
    }

    previews = build_previews(info)

    assert len(previews) == 1
    assert previews[0]["insert_before_paragraph_index"] is None
    assert previews[0]["insert_before_paragraph_id"] is None
    assert previews[0]["insert_after_paragraph_index"] is None  # No paragraph to insert after
    assert previews[0]["insert_after_paragraph_id"] is None
    assert previews[0]["position"] == "end"


def test_build_previews_none_missing():
    """Test build_previews when no sections are missing."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [],
    }

    previews = build_previews(info)

    assert len(previews) == 0
    assert previews == []


def test_build_previews_unreliable():
    """Test build_previews when detection is unreliable."""
    from missing_sections import build_previews

    info = {
        "reliable": False,
        "reason": "Too few headings detected",
        "missing": [
            {
                "name": "Abstract",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": 5,
            }
        ],
    }

    # Should still build previews even if unreliable (caller decides whether to use them)
    previews = build_previews(info)

    assert len(previews) == 1
    assert previews[0]["name"] == "Abstract"


def test_build_previews_section_with_special_chars():
    """Test build_previews with section name containing special characters."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [
            {
                "name": "Problem Statement & Objectives",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": 3,
            }
        ],
    }

    previews = build_previews(info)

    assert len(previews) == 1
    # Same helper as heading_matches_to_issues (normalize, do not slugify)
    assert previews[0]["issue_id"] == "missing_heading_problem statement & objectives"
    assert previews[0]["name"] == "Problem Statement & Objectives"


def test_build_previews_optional_section():
    """Test build_previews with an optional section."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [
            {
                "name": "Appendix",
                "level": 1,
                "optional": True,
                "insert_before_paragraph_index": 10,
            }
        ],
    }

    previews = build_previews(info)

    assert len(previews) == 1
    assert previews[0]["optional"] is True
    assert previews[0]["name"] == "Appendix"


def test_section_guidance_abstract():
    """Test _section_guidance returns specific guidance for Abstract."""
    from missing_sections import _section_guidance

    guidance = _section_guidance("Abstract")
    assert "150-250 words" in guidance
    assert "Summarize the problem" in guidance


def test_section_guidance_unknown_section():
    """Test _section_guidance returns generic guidance for unknown sections."""
    from missing_sections import _section_guidance

    guidance = _section_guidance("Custom Section")
    assert "Custom Section" in guidance
    assert "template guidelines" in guidance


def test_build_previews_backward_compatibility():
    """Test that build_previews maintains backward compatibility with existing fields."""
    from missing_sections import build_previews

    info = {
        "reliable": True,
        "reason": "",
        "missing": [
            {
                "name": "Abstract",
                "level": 1,
                "optional": False,
                "insert_before_paragraph_index": 5,
            }
        ],
    }

    previews = build_previews(info)

    # Original fields that should still exist
    assert "name" in previews[0]
    assert "level" in previews[0]
    assert "optional" in previews[0]
    assert "insert_before_paragraph_index" in previews[0]
    assert "insert_before_paragraph_id" in previews[0]
    assert "position" in previews[0]
    assert "placeholder_text" in previews[0]
    assert "suggested_content" in previews[0]

    # New fields
    assert "issue_id" in previews[0]
    assert "is_placeholder" in previews[0]
    assert "insert_after_paragraph_index" in previews[0]
    assert "insert_after_paragraph_id" in previews[0]
    assert "guidance_text" in previews[0]


def test_normalize_required_sections_filters_frontmatter():
    """Test that normalize_required_sections filters out front-matter entries."""
    from missing_sections import normalize_required_sections

    # Template with front-matter and body sections
    sections = [
        "Title Page",
        "Declaration",
        "Table of Contents",
        "List of Figures",
        "List of Tables",
        "Abstract",
        "Introduction",
        "Methodology",
        "Results",
        "Conclusion",
        "References",
        "Appendix",
    ]

    normalized = normalize_required_sections(sections)

    # Front-matter entries should be filtered out
    frontmatter_names = {"title page", "declaration", "table of contents", 
                        "list of figures", "list of tables"}
    for section in normalized:
        assert section["name"].lower() not in frontmatter_names
    
    # Body sections should remain
    body_names = {"abstract", "introduction", "methodology", "results", 
                  "conclusion", "references", "appendix"}
    normalized_names = {s["name"].lower() for s in normalized}
    for name in body_names:
        assert name in normalized_names


def test_is_frontmatter_section():
    """Test _is_frontmatter_section correctly identifies front-matter entries."""
    from missing_sections import _is_frontmatter_section

    # Front-matter entries
    assert _is_frontmatter_section("Title Page") is True
    assert _is_frontmatter_section("Cover Page") is True
    assert _is_frontmatter_section("Declaration") is True
    assert _is_frontmatter_section("Certification") is True
    assert _is_frontmatter_section("Table of Contents") is True
    assert _is_frontmatter_section("Contents") is True
    assert _is_frontmatter_section("List of Figures") is True
    assert _is_frontmatter_section("List of Tables") is True
    assert _is_frontmatter_section("List of Abbreviations") is True
    assert _is_frontmatter_section("{{ logo }}") is True

    # Body sections (should return False)
    assert _is_frontmatter_section("Abstract") is False
    assert _is_frontmatter_section("Introduction") is False
    assert _is_frontmatter_section("Methodology") is False
    assert _is_frontmatter_section("Results") is False
    assert _is_frontmatter_section("Conclusion") is False
    assert _is_frontmatter_section("References") is False
    assert _is_frontmatter_section("Appendix") is False


def test_normalize_required_sections_with_dict():
    """Test normalize_required_sections with dict input and front-matter filtering."""
    from missing_sections import normalize_required_sections

    sections = [
        {"name": "Title Page", "level": 1},
        {"name": "Abstract", "level": 1},
        {"name": "Introduction", "level": 1},
        {"name": "Table of Contents", "level": 1},
        {"name": "Methodology", "level": 1},
    ]

    normalized = normalize_required_sections(sections)

    # Should only include body sections
    assert len(normalized) == 3
    normalized_names = [s["name"] for s in normalized]
    assert "Abstract" in normalized_names
    assert "Introduction" in normalized_names
    assert "Methodology" in normalized_names
    assert "Title Page" not in normalized_names
    assert "Table of Contents" not in normalized_names


def test_build_template_outline_filters_frontmatter():
    """Test that build_template_outline filters out front-matter entries."""
    from docx_tools.heading_analysis import build_template_outline

    sections = [
        "Title Page",
        "Declaration",
        "Table of Contents",
        "Abstract",
        "Introduction",
        "Methodology",
    ]

    outline = build_template_outline(sections)

    # Front-matter should be filtered out
    outline_names = [entry.name for entry in outline]
    assert "Title Page" not in outline_names
    assert "Declaration" not in outline_names
    assert "Table of Contents" not in outline_names
    
    # Body sections should remain
    assert "Abstract" in outline_names
    assert "Introduction" in outline_names
    assert "Methodology" in outline_names


def test_heading_analysis_is_frontmatter_section():
    """Test _is_frontmatter_section in heading_analysis."""
    from docx_tools.heading_analysis import _is_frontmatter_section

    # Front-matter entries
    assert _is_frontmatter_section("Title Page") is True
    assert _is_frontmatter_section("Cover Page") is True
    assert _is_frontmatter_section("Declaration") is True
    assert _is_frontmatter_section("Table of Contents") is True
    assert _is_frontmatter_section("List of Figures") is True

    # Body sections
    assert _is_frontmatter_section("Abstract") is False
    assert _is_frontmatter_section("Introduction") is False
    assert _is_frontmatter_section("Methodology") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
