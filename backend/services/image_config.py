"""Image formatting config defaults from template formatting_rules."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.captioned_element_config import (
    clamp_percent,
    format_caption_label as shared_format_caption_label,
    normalize_caption_position,
    normalize_numbering_scheme,
    resolve_caption_pattern,
)

DEFAULT_FIGURE_CAPTION_GLOBAL = "Figure {n}: {caption}"
DEFAULT_FIGURE_CAPTION_CHAPTER = "Figure {chapter}.{n}: {caption}"

DEFAULT_IMAGE_FORMAT_RULES: Dict[str, Any] = {
    "caption_format_pattern": DEFAULT_FIGURE_CAPTION_GLOBAL,
    "numbering_scheme": "global",  # global | chapter
    "caption_position": "below",  # above | below
    "max_image_width_percent": 80,
    "include_lof": True,
    "require_caption": True,
    "require_intext_reference": False,
}


def get_image_format_config(formatting_rules: Dict[str, Any] | None) -> Dict[str, Any]:
    """Merge template formatting_rules with image-format defaults."""
    rules = dict(DEFAULT_IMAGE_FORMAT_RULES)
    src = formatting_rules or {}
    for key in DEFAULT_IMAGE_FORMAT_RULES:
        if key in src and src[key] is not None and src[key] != "":
            rules[key] = src[key]

    rules["numbering_scheme"] = normalize_numbering_scheme(rules.get("numbering_scheme"))
    rules["caption_position"] = normalize_caption_position(
        rules.get("caption_position"), default="below"
    )
    rules["max_image_width_percent"] = clamp_percent(
        rules.get("max_image_width_percent"), default=80, lo=10, hi=100
    )
    rules["caption_format_pattern"] = resolve_caption_pattern(
        rules.get("caption_format_pattern"),
        numbering_scheme=rules["numbering_scheme"],
        default_global=DEFAULT_FIGURE_CAPTION_GLOBAL,
        default_chapter=DEFAULT_FIGURE_CAPTION_CHAPTER,
    )
    rules["include_lof"] = bool(src.get("include_lof", rules["include_lof"]))
    rules["require_caption"] = bool(src.get("require_caption", rules["require_caption"]))
    rules["require_intext_reference"] = bool(
        src.get("require_intext_reference", rules["require_intext_reference"])
    )
    return rules


def format_caption_label(
    *,
    pattern: str,
    n: int,
    chapter: Optional[int],
    caption: str,
) -> str:
    """Fill admin caption pattern. Unknown placeholders are left blank."""
    return shared_format_caption_label(
        pattern=pattern,
        n=n,
        chapter=chapter,
        caption=caption,
        fallback_label="Figure",
    )
