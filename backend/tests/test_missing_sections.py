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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
