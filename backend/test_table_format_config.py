"""Smoke tests for table format config + shared caption helpers."""

from __future__ import annotations

from services.captioned_element_config import (
    format_caption_label,
    normalize_numbering_scheme,
    resolve_caption_pattern,
)
from services.image_config import get_image_format_config
from services.table_config import (
    get_table_format_config,
    normalize_formatting_rules_table_section,
    validate_table_format_rules,
)


def test_shared_numbering_and_pattern() -> None:
    assert normalize_numbering_scheme("chapter_wise") == "chapter"
    assert normalize_numbering_scheme("GLOBAL") == "global"
    pat = resolve_caption_pattern(
        "Figure {n}: {caption}",
        numbering_scheme="chapter",
        default_global="Figure {n}: {caption}",
        default_chapter="Figure {chapter}.{n}: {caption}",
    )
    assert "{chapter}" in pat
    label = format_caption_label(
        pattern="Table {n}: {description}",
        n=2,
        chapter=None,
        caption="Results",
        fallback_label="Table",
    )
    assert label == "Table 2: Results"


def test_table_defaults_and_validation() -> None:
    cfg = get_table_format_config({})
    assert cfg["table_caption_position"] == "above"
    assert cfg["table_numbering_scheme"] == "global"
    assert cfg["include_lot"] is True
    assert cfg["table_style"]["max_width_percent"] == 100
    assert cfg["table_style"]["border_style"] == "academic_standard"

    bad = {
        "table_caption_position": "sideways",
        "table_style": {"max_width_percent": 150, "border_style": "fancy"},
    }
    errs = validate_table_format_rules(bad)
    assert any("caption_position" in e for e in errs)
    assert any("max_width_percent" in e for e in errs)
    assert any("border_style" in e for e in errs)

    normalized = normalize_formatting_rules_table_section(
        {
            "heading1_size": 18,
            "table_numbering_scheme": "chapter-wise",
            "table_style": {"borders": False},
        }
    )
    assert normalized["heading1_size"] == 18
    assert normalized["table_numbering_scheme"] == "chapter"
    assert normalized["table_style"]["border_style"] == "none"
    assert "{chapter}" in normalized["table_caption_format_pattern"]


def test_image_config_still_works() -> None:
    cfg = get_image_format_config(
        {"numbering_scheme": "chapter", "include_lof": False}
    )
    assert cfg["numbering_scheme"] == "chapter"
    assert cfg["include_lof"] is False
    assert cfg["caption_position"] == "below"
    assert "require_caption" in cfg


if __name__ == "__main__":
    test_shared_numbering_and_pattern()
    test_table_defaults_and_validation()
    test_image_config_still_works()
    print("ALL TABLE CONFIG ASSERTIONS PASSED")
