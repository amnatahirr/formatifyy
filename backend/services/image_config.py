"""Image formatting config defaults from template formatting_rules."""

from __future__ import annotations

from typing import Any, Dict


DEFAULT_IMAGE_FORMAT_RULES: Dict[str, Any] = {
    "caption_format_pattern": "Figure {n}: {caption}",
    "numbering_scheme": "global",  # global | chapter
    "caption_position": "below",  # above | below
    "max_image_width_percent": 80,
    "include_lof": True,
}


def get_image_format_config(formatting_rules: Dict[str, Any] | None) -> Dict[str, Any]:
    """Merge template formatting_rules with image-format defaults."""
    rules = dict(DEFAULT_IMAGE_FORMAT_RULES)
    src = formatting_rules or {}
    for key in DEFAULT_IMAGE_FORMAT_RULES:
        if key in src and src[key] is not None and src[key] != "":
            rules[key] = src[key]

    scheme = str(rules.get("numbering_scheme", "global")).strip().lower()
    if scheme in ("chapter", "chapter-wise", "chapter_wise"):
        rules["numbering_scheme"] = "chapter"
    else:
        rules["numbering_scheme"] = "global"

    pos = str(rules.get("caption_position", "below")).strip().lower()
    rules["caption_position"] = "above" if pos == "above" else "below"

    try:
        pct = int(rules.get("max_image_width_percent", 80))
    except (TypeError, ValueError):
        pct = 80
    rules["max_image_width_percent"] = max(10, min(100, pct))

    pattern = str(rules.get("caption_format_pattern") or "").strip()
    if not pattern:
        if rules["numbering_scheme"] == "chapter":
            pattern = "Figure {chapter}.{n}: {caption}"
        else:
            pattern = "Figure {n}: {caption}"
    elif rules["numbering_scheme"] == "chapter" and "{chapter}" not in pattern:
        # Admin picked chapter scheme but left the global default pattern.
        if pattern == DEFAULT_IMAGE_FORMAT_RULES["caption_format_pattern"]:
            pattern = "Figure {chapter}.{n}: {caption}"
    rules["caption_format_pattern"] = pattern

    rules["include_lof"] = bool(src.get("include_lof", rules["include_lof"]))
    return rules


def format_caption_label(
    *,
    pattern: str,
    n: int,
    chapter: int | None,
    caption: str,
) -> str:
    """Fill admin caption pattern. Unknown placeholders are left blank."""
    desc = (caption or "").strip()
    try:
        return pattern.format(
            n=n,
            chapter=chapter if chapter is not None else "",
            caption=desc,
        ).strip()
    except (KeyError, ValueError, IndexError):
        if chapter is not None:
            return f"Figure {chapter}.{n}: {desc}".strip(": ").strip()
        return f"Figure {n}: {desc}".strip(": ").strip()
