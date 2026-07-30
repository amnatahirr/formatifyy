"""
Table formatting config defaults from template formatting_rules.

Flat keys:
  table_caption_position, table_caption_format_pattern, table_numbering_scheme,
  include_lot, table_require_caption, table_require_intext_reference,
  list_of_tables_format
Nested:
  formatting_rules.table_style { ... }
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.captioned_element_config import (
    clamp_percent,
    format_caption_label,
    merge_captioned_fields,
    normalize_caption_position,
    normalize_numbering_scheme,
    resolve_caption_pattern,
    validate_captioned_fields,
)

BORDER_STYLES = frozenset(
    {"none", "single_line", "double_line", "academic_standard"}
)
ALIGNMENTS = frozenset({"left", "center", "right", "justify"})
WIDE_TABLE_STRATEGIES = frozenset(
    {"shrink_font", "landscape_page", "flag_for_manual_review"}
)
ROW_HEIGHT_POLICIES = frozenset({"auto", "fixed_minimum"})
PAGE_ALIGNMENTS = frozenset({"center", "left"})

DEFAULT_TABLE_CAPTION_GLOBAL = "Table {n}: {description}"
DEFAULT_TABLE_CAPTION_CHAPTER = "Table {chapter}.{n}: {description}"

DEFAULT_TABLE_STYLE: Dict[str, Any] = {
    # Existing fields (TableStylesCard)
    "font_name": "Times New Roman",
    "font_size": 12,
    "header_bold": False,
    "header_bg": "FFFFFF",
    "header_align": "center",
    "body_align": "left",
    "banded_rows": False,
    "band_color": "F2F8FC",
    "borders": True,
    "border_color": "000000",
    "border_size": 4,
    "cell_padding_top": 60,
    "cell_padding_bot": 60,
    "cell_padding_lft": 108,
    "cell_padding_rgt": 108,
    "center_table": True,
    "auto_fit": True,
    "repeat_header": True,
    # New — borders & style
    "border_style": "academic_standard",
    "header_row_shading": False,
    "border_thickness": 4,  # mirrors border_size when set
    # New — sizing
    "max_width_percent": 100,
    "min_column_width": 0.5,  # inches
    "wide_table_handling": "flag_for_manual_review",
    # New — cell formatting
    "numeric_column_alignment": "left",
    "text_column_alignment": "left",
    "row_height_policy": "auto",
    # New — layout
    "space_before": 6.0,  # pt
    "space_after": 6.0,
    "alignment_on_page": "center",
    # New — validation threshold (table-only)
    "max_empty_cell_percent": 30,
}

# Top-level flat keys (merged view uses logical names in get_table_format_config)
DEFAULT_TABLE_FORMAT_RULES: Dict[str, Any] = {
    "table_caption_position": "above",
    "table_caption_format_pattern": DEFAULT_TABLE_CAPTION_GLOBAL,
    "table_numbering_scheme": "global",
    "include_lot": True,
    "table_require_caption": True,
    "table_require_intext_reference": False,
    "list_of_tables_format": DEFAULT_TABLE_CAPTION_GLOBAL,
    "table_style": dict(DEFAULT_TABLE_STYLE),
}

_TABLE_CAPTION_KEY_MAP = {
    "caption_position": "table_caption_position",
    "caption_format_pattern": "table_caption_format_pattern",
    "numbering_scheme": "table_numbering_scheme",
    "require_caption": "table_require_caption",
    "require_intext_reference": "table_require_intext_reference",
    "include_list": "include_lot",
    "list_format": "list_of_tables_format",
}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_hex_color(value: Any, default: str) -> str:
    raw = str(value if value is not None else default).strip().lstrip("#")
    if len(raw) == 6 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return raw.upper()
    return default.lstrip("#").upper()


def _normalize_align(value: Any, default: str) -> str:
    v = str(value or default).strip().lower()
    return v if v in ALIGNMENTS else default


def merge_table_style(raw: Any) -> Dict[str, Any]:
    """Merge a table_style dict with defaults and normalize enums."""
    style = dict(DEFAULT_TABLE_STYLE)
    src = raw if isinstance(raw, dict) else {}
    for key, default in DEFAULT_TABLE_STYLE.items():
        if key not in src or src[key] is None or src[key] == "":
            continue
        style[key] = src[key]

    # Bools
    for bk in (
        "header_bold",
        "banded_rows",
        "borders",
        "center_table",
        "auto_fit",
        "repeat_header",
        "header_row_shading",
    ):
        style[bk] = _as_bool(style.get(bk), bool(DEFAULT_TABLE_STYLE[bk]))

    # Alignments
    style["header_align"] = _normalize_align(style.get("header_align"), "center")
    style["body_align"] = _normalize_align(style.get("body_align"), "left")
    style["numeric_column_alignment"] = _normalize_align(
        style.get("numeric_column_alignment"), "right"
    )
    style["text_column_alignment"] = _normalize_align(
        style.get("text_column_alignment"), "left"
    )

    page_align = str(style.get("alignment_on_page") or "").strip().lower()
    if page_align not in PAGE_ALIGNMENTS:
        # Derive from legacy center_table
        page_align = "center" if style.get("center_table") else "left"
    style["alignment_on_page"] = page_align
    style["center_table"] = page_align == "center"

    border_style = str(style.get("border_style") or "").strip().lower()
    if "border_style" not in src or src.get("border_style") in (None, ""):
        # Derive from legacy borders bool when style not explicitly set
        border_style = "none" if not style.get("borders") else "academic_standard"
    elif border_style not in BORDER_STYLES:
        border_style = "none" if not style.get("borders") else "academic_standard"
    style["border_style"] = border_style
    if border_style == "none":
        style["borders"] = False
    else:
        style["borders"] = True

    wide = str(style.get("wide_table_handling") or "").strip().lower()
    if wide not in WIDE_TABLE_STRATEGIES:
        wide = "flag_for_manual_review"
    style["wide_table_handling"] = wide

    rh = str(style.get("row_height_policy") or "").strip().lower()
    if rh not in ROW_HEIGHT_POLICIES:
        rh = "auto"
    style["row_height_policy"] = rh

    style["font_size"] = max(6, min(72, _as_int(style.get("font_size"), 12)))
    style["border_size"] = max(0, min(48, _as_int(style.get("border_size"), 4)))
    thickness = style.get("border_thickness", style["border_size"])
    style["border_thickness"] = max(0, min(48, _as_int(thickness, style["border_size"])))
    # Keep border_size in sync for older consumers
    style["border_size"] = style["border_thickness"]

    style["max_width_percent"] = clamp_percent(
        style.get("max_width_percent"), default=100, lo=10, hi=100
    )
    style["max_empty_cell_percent"] = clamp_percent(
        style.get("max_empty_cell_percent"), default=30, lo=0, hi=100
    )
    style["min_column_width"] = max(0.0, _as_float(style.get("min_column_width"), 0.5))
    style["space_before"] = max(0.0, _as_float(style.get("space_before"), 6.0))
    style["space_after"] = max(0.0, _as_float(style.get("space_after"), 6.0))

    for pk in (
        "cell_padding_top",
        "cell_padding_bot",
        "cell_padding_lft",
        "cell_padding_rgt",
    ):
        style[pk] = max(0, _as_int(style.get(pk), int(DEFAULT_TABLE_STYLE[pk])))

    style["header_bg"] = _normalize_hex_color(style.get("header_bg"), "D6E4F0")
    style["band_color"] = _normalize_hex_color(style.get("band_color"), "F2F8FC")
    style["border_color"] = _normalize_hex_color(style.get("border_color"), "000000")
    style["font_name"] = str(style.get("font_name") or "Times New Roman").strip()

    if not style.get("header_row_shading"):
        # Shading off — keep color stored but consumers should ignore fill
        pass

    return style


def get_table_format_config(formatting_rules: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Merge template formatting_rules with table-format defaults.

    Returns a normalized dict with both flat caption keys and nested table_style,
    plus a convenient 'captioned' logical view for shared helpers.
    """
    src = formatting_rules or {}
    caption_defaults = {
        "caption_position": "above",
        "caption_format_pattern": DEFAULT_TABLE_CAPTION_GLOBAL,
        "numbering_scheme": "global",
        "require_caption": True,
        "require_intext_reference": False,
        "include_list": True,
        "list_format": DEFAULT_TABLE_CAPTION_GLOBAL,
    }
    captioned = merge_captioned_fields(src, caption_defaults, key_map=_TABLE_CAPTION_KEY_MAP)

    scheme = normalize_numbering_scheme(captioned.get("numbering_scheme"))
    captioned["numbering_scheme"] = scheme
    captioned["caption_position"] = normalize_caption_position(
        captioned.get("caption_position"), default="above"
    )
    captioned["caption_format_pattern"] = resolve_caption_pattern(
        captioned.get("caption_format_pattern"),
        numbering_scheme=scheme,
        default_global=DEFAULT_TABLE_CAPTION_GLOBAL,
        default_chapter=DEFAULT_TABLE_CAPTION_CHAPTER,
    )
    captioned["require_caption"] = _as_bool(captioned.get("require_caption"), True)
    captioned["require_intext_reference"] = _as_bool(
        captioned.get("require_intext_reference"), False
    )
    captioned["include_list"] = _as_bool(
        captioned.get("include_list"),
        _as_bool(src.get("include_lot"), True),
    )
    list_fmt = str(captioned.get("list_format") or "").strip()
    if not list_fmt:
        list_fmt = captioned["caption_format_pattern"]
    captioned["list_format"] = list_fmt

    style = merge_table_style(src.get("table_style"))

    return {
        # Flat keys (persist / admin)
        "table_caption_position": captioned["caption_position"],
        "table_caption_format_pattern": captioned["caption_format_pattern"],
        "table_numbering_scheme": captioned["numbering_scheme"],
        "include_lot": captioned["include_list"],
        "table_require_caption": captioned["require_caption"],
        "table_require_intext_reference": captioned["require_intext_reference"],
        "list_of_tables_format": captioned["list_format"],
        "table_style": style,
        # Logical shared view
        "captioned": captioned,
    }


def format_table_caption_label(
    *,
    pattern: str,
    n: int,
    chapter: Optional[int],
    description: str,
) -> str:
    return format_caption_label(
        pattern=pattern,
        n=n,
        chapter=chapter,
        caption=description,
        fallback_label="Table",
    )


def validate_table_format_rules(formatting_rules: Dict[str, Any] | None) -> List[str]:
    """Validate table-related keys on a formatting_rules dict. Returns errors."""
    if not formatting_rules:
        return []
    errors: List[str] = []
    src = formatting_rules

    # Caption flat keys
    probe = {
        "numbering_scheme": src.get("table_numbering_scheme"),
        "caption_position": src.get("table_caption_position"),
        "require_caption": src.get("table_require_caption"),
        "require_intext_reference": src.get("table_require_intext_reference"),
    }
    # Only validate keys that are present
    present = {k: v for k, v in probe.items() if k in (
        "numbering_scheme", "caption_position", "require_caption", "require_intext_reference"
    ) and (
        (k == "numbering_scheme" and "table_numbering_scheme" in src)
        or (k == "caption_position" and "table_caption_position" in src)
        or (k == "require_caption" and "table_require_caption" in src)
        or (k == "require_intext_reference" and "table_require_intext_reference" in src)
    )}
    errors.extend(validate_captioned_fields(present, prefix="table"))

    if "include_lot" in src and src["include_lot"] is not None:
        src["include_lot"] = _as_bool(src["include_lot"], True)

    if "table_style" in src and src["table_style"] is not None:
        if not isinstance(src["table_style"], dict):
            errors.append("table_style must be an object")
        else:
            ts = src["table_style"]
            if "border_style" in ts and ts["border_style"] is not None:
                bs = str(ts["border_style"]).strip().lower()
                if bs not in BORDER_STYLES:
                    errors.append(
                        "table_style.border_style must be one of: "
                        + ", ".join(sorted(BORDER_STYLES))
                    )
            if "wide_table_handling" in ts and ts["wide_table_handling"] is not None:
                w = str(ts["wide_table_handling"]).strip().lower()
                if w not in WIDE_TABLE_STRATEGIES:
                    errors.append(
                        "table_style.wide_table_handling must be one of: "
                        + ", ".join(sorted(WIDE_TABLE_STRATEGIES))
                    )
            if "row_height_policy" in ts and ts["row_height_policy"] is not None:
                rh = str(ts["row_height_policy"]).strip().lower()
                if rh not in ROW_HEIGHT_POLICIES:
                    errors.append(
                        "table_style.row_height_policy must be 'auto' or 'fixed_minimum'"
                    )
            if "alignment_on_page" in ts and ts["alignment_on_page"] is not None:
                a = str(ts["alignment_on_page"]).strip().lower()
                if a not in PAGE_ALIGNMENTS:
                    errors.append(
                        "table_style.alignment_on_page must be 'center' or 'left'"
                    )
            for pct_key in ("max_width_percent", "max_empty_cell_percent"):
                if pct_key in ts and ts[pct_key] is not None:
                    try:
                        pct = int(ts[pct_key])
                    except (TypeError, ValueError):
                        errors.append(f"table_style.{pct_key} must be an integer")
                        continue
                    if pct < 0 or pct > 100:
                        errors.append(f"table_style.{pct_key} must be between 0 and 100")

    return errors


def normalize_formatting_rules_table_section(
    formatting_rules: Dict[str, Any],
) -> Dict[str, Any]:
    """
    In-place friendly: return a copy of formatting_rules with table keys normalized.
    Non-table keys are preserved unchanged.
    """
    out = dict(formatting_rules or {})
    cfg = get_table_format_config(out)
    out["table_caption_position"] = cfg["table_caption_position"]
    out["table_caption_format_pattern"] = cfg["table_caption_format_pattern"]
    out["table_numbering_scheme"] = cfg["table_numbering_scheme"]
    out["include_lot"] = cfg["include_lot"]
    out["table_require_caption"] = cfg["table_require_caption"]
    out["table_require_intext_reference"] = cfg["table_require_intext_reference"]
    out["list_of_tables_format"] = cfg["list_of_tables_format"]
    out["table_style"] = cfg["table_style"]
    return out
