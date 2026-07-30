"""
Shared caption / numbering helpers for figures and tables.

DB keys stay flat and separate (figure vs table_*). This module only
reuses validation and merge logic at the code level.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

ElementType = Literal["figure", "table"]

NUMBERING_SCHEMES = frozenset({"global", "chapter"})
CAPTION_POSITIONS = frozenset({"above", "below"})


def normalize_numbering_scheme(value: Any, *, default: str = "global") -> str:
    """Normalize admin numbering scheme to 'global' | 'chapter'."""
    scheme = str(value or default).strip().lower()
    if scheme in ("chapter", "chapter-wise", "chapter_wise"):
        return "chapter"
    return "global"


def normalize_caption_position(value: Any, *, default: str = "below") -> str:
    pos = str(value or default).strip().lower()
    return "above" if pos == "above" else "below"


def clamp_percent(value: Any, *, default: int, lo: int = 0, hi: int = 100) -> int:
    try:
        pct = int(value)
    except (TypeError, ValueError):
        pct = default
    return max(lo, min(hi, pct))


def resolve_caption_pattern(
    pattern: Any,
    *,
    numbering_scheme: str,
    default_global: str,
    default_chapter: str,
) -> str:
    """
    Pick / repair caption format pattern for the active numbering scheme.
    If admin left the global default while scheme is chapter, upgrade pattern.
    """
    text = str(pattern or "").strip()
    if not text:
        return default_chapter if numbering_scheme == "chapter" else default_global
    if numbering_scheme == "chapter" and "{chapter}" not in text:
        if text == default_global:
            return default_chapter
    return text


def format_caption_label(
    *,
    pattern: str,
    n: int,
    chapter: Optional[int],
    caption: str,
    fallback_label: str = "Figure",
) -> str:
    """Fill caption pattern placeholders. Unknown keys become blank."""
    desc = (caption or "").strip()
    try:
        return pattern.format(
            n=n,
            number=n,
            chapter=chapter if chapter is not None else "",
            caption=desc,
            description=desc,
        ).strip()
    except (KeyError, ValueError, IndexError):
        if chapter is not None:
            return f"{fallback_label} {chapter}.{n}: {desc}".strip(": ").strip()
        return f"{fallback_label} {n}: {desc}".strip(": ").strip()


def merge_captioned_fields(
    src: Dict[str, Any],
    defaults: Dict[str, Any],
    *,
    key_map: Dict[str, str],
) -> Dict[str, Any]:
    """
    Merge flat formatting_rules keys into a captioned-element view.

    key_map: logical_name -> formatting_rules key
      e.g. {"caption_position": "table_caption_position"}
    """
    out = dict(defaults)
    for logical, rules_key in key_map.items():
        if rules_key in src and src[rules_key] is not None and src[rules_key] != "":
            out[logical] = src[rules_key]
        elif logical in src and src[logical] is not None and src[logical] != "":
            # Allow reading already-normalized logical keys
            out[logical] = src[logical]
    return out


def validate_captioned_fields(
    data: Dict[str, Any],
    *,
    prefix: str = "",
) -> list[str]:
    """Return list of validation error strings (empty if OK)."""
    errors: list[str] = []
    label = f"{prefix} " if prefix else ""

    if "numbering_scheme" in data and data["numbering_scheme"] is not None:
        scheme = normalize_numbering_scheme(data["numbering_scheme"])
        raw = str(data["numbering_scheme"]).strip().lower()
        if raw and raw not in (
            "global",
            "chapter",
            "chapter-wise",
            "chapter_wise",
        ):
            errors.append(f"{label}numbering_scheme must be 'global' or 'chapter'")
        data["numbering_scheme"] = scheme

    if "caption_position" in data and data["caption_position"] is not None:
        pos = str(data["caption_position"]).strip().lower()
        if pos not in CAPTION_POSITIONS:
            errors.append(f"{label}caption_position must be 'above' or 'below'")
        else:
            data["caption_position"] = pos

    for bool_key in ("require_caption", "require_intext_reference", "include_list"):
        if bool_key in data and data[bool_key] is not None:
            data[bool_key] = bool(data[bool_key])

    return errors
