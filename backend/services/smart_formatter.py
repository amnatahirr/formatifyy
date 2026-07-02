"""
services/smart_formatter.py
────────────────────────────
Template-Rule Application Engine.

Takes the classified block list from detector.py + classifier.py and
produces the final structured JSON that the API returns and Flutter renders.

This module does NOT generate DOCX / PDF files — that is done by the
existing docx_generator.py and pdf_generator.py.  This module is solely
responsible for computing the *style dict* for each block so the frontend
can render a live preview and so the generators receive a complete spec.

Integration points
──────────────────
• Input  : classified blocks (List[Dict]) + template_rules (Dict | None)
• Output : List[FormattedElement]  (serialised as JSON by the API)
• Used by: routers/format_document.py
• Reads template rules via database.get_db()  OR  accepts them directly.

Output schema (one element)
───────────────────────────
{
    "index":    0,
    "type":     "heading",        # heading | paragraph | toc | formula | list_item
    "level":    "H2",             # only for headings, else null
    "text":     "Introduction",
    "style": {
        "font_name":     "Times New Roman",
        "font_size":     14,
        "bold":          true,
        "italic":        false,
        "underline":     false,
        "color":         "#000000",
        "alignment":     "left",
        "line_spacing":  1.5,
        "space_before":  10.0,
        "space_after":   5.0,
        "indent_left":   0.0
    }
}
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from database import get_db


# ── Default style templates ───────────────────────────────────────────────────
# These mirror paragraph_formatter.py's _get_default_rules() so the two
# pipelines stay in sync.

_LEVEL_KEY = {1: "heading1", 2: "heading2", 3: "heading3", 4: "heading4"}

_ALIGNMENT_MAP = {
    "left":    "left",
    "center":  "center",
    "centre":  "center",
    "right":   "right",
    "justify": "justify",
    "justified": "justify",
}


class SmartFormatter:
    """
    Applies template rules to a list of classified blocks and returns
    structured JSON-serialisable dicts.
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def format_blocks(
        self,
        blocks:       List[Dict[str, Any]],
        template_id:  Optional[int]  = None,
        template_rules: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parameters
        ----------
        blocks        : classified block list from detector + classifier
        template_id   : if provided, rules are fetched from the database
        template_rules: if provided directly, DB lookup is skipped

        Returns
        -------
        List of FormattedElement dicts ready for JSON serialisation.
        """
        rules = self._resolve_rules(template_id, template_rules)
        return [self._format_block(b, rules) for b in blocks]

    # ── Rule resolution ───────────────────────────────────────────────────────

    def _resolve_rules(
        self,
        template_id:    Optional[int],
        template_rules: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Priority: direct template_rules > DB lookup > built-in defaults.
        """
        if template_rules:
            return self._merge_with_defaults(template_rules)

        if template_id is not None:
            db_rules = self._fetch_rules_from_db(template_id)
            if db_rules:
                return self._merge_with_defaults(db_rules)

        return self._default_rules()

    def _fetch_rules_from_db(self, template_id: int) -> Optional[Dict[str, Any]]:
        """Fetch formatting_rules JSON from the templates table."""
        try:
            conn = get_db()
            row  = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (template_id,),
            ).fetchone()
            conn.close()

            if row and row["formatting_rules"]:
                rules = json.loads(row["formatting_rules"])
                return rules if isinstance(rules, dict) else None

        except Exception as exc:
            print(f"[SmartFormatter] DB fetch failed: {exc}")

        return None

    # ── Block formatter ───────────────────────────────────────────────────────

    def _format_block(
        self,
        block: Dict[str, Any],
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Produce one FormattedElement dict."""

        btype = block.get("type", "paragraph")
        text  = block.get("raw_text", "").strip()
        index = block.get("index", 0)

        if btype == "heading":
            level_int = block.get("level", 1)
            level_int = max(1, min(4, level_int))
            style     = self._heading_style(level_int, rules)
            level_str = f"H{level_int}"

        elif btype == "toc":
            style     = self._toc_style(rules)
            level_str = None

        elif btype == "formula":
            style     = self._formula_style(rules)
            level_str = None

        elif btype == "list_item":
            style     = self._list_item_style(rules)
            level_str = None
        elif btype == "figure":
            style     = self._figure_style(rules)
            level_str = None
        elif btype == "caption":
            style     = self._caption_style(rules)
            level_str = None
        elif btype == "reference":
            style     = self._reference_style(rules)
            level_str = None

        else:  # paragraph (default)
            style     = self._paragraph_style(rules)
            level_str = None

        return {
            "index": index,
            "type":  btype,
            "level": level_str,
            "text":  text,
            "style": style,
        }

    # ── Style builders ────────────────────────────────────────────────────────

    def _heading_style(self, level: int, rules: Dict[str, Any]) -> Dict[str, Any]:
        prefix = _LEVEL_KEY[level]          # e.g. "heading2"

        return {
            "font_name":    rules.get(f"{prefix}_font",         "Times New Roman"),
            "font_size":    rules.get(f"{prefix}_size",         self._default_heading_size(level)),
            "bold":         rules.get(f"{prefix}_bold",         True),
            "italic":       rules.get(f"{prefix}_italic",       False),  # Now user-configurable
            "underline":    rules.get(f"{prefix}_underline",    False),
            "color":        rules.get(f"{prefix}_color",        "#000000"),
            "alignment":    _ALIGNMENT_MAP.get(
                                rules.get(f"{prefix}_alignment", "left"), "left"),
            "line_spacing": rules.get(f"{prefix}_line_spacing", 1.5),
            "space_before": self._convert_spacing_value(rules.get(f"{prefix}_space_before", self._default_space_before(level)), rules),
            "space_after":  self._convert_spacing_value(rules.get(f"{prefix}_space_after", self._default_space_after(level)), rules),
            "indent_left":  0.0,
            "spacing_unit": rules.get("spacing_unit", "mm"),  # Include unit info
        }

    def _paragraph_style(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "font_name":    rules.get("body_font",          "Times New Roman"),
            "font_size":    rules.get("body_size",          11),
            "bold":         False,
            "italic":       False,
            "underline":    False,
            "color":        rules.get("body_color",         "#000000"),
            "alignment":    _ALIGNMENT_MAP.get(
                                rules.get("body_alignment", "justify"), "justify"),
            "line_spacing": rules.get("body_line_spacing",  1.0),
            "space_before": rules.get("body_space_before",  0.0),
            "space_after":  rules.get("body_space_after",   6.0),
            "indent_left":  rules.get("first_line_indent",  0.5),
        }

    def _list_item_style(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "font_name":    rules.get("bullet_font",           "Times New Roman"),
            "font_size":    rules.get("bullet_size",           12),
            "bold":         False,
            "italic":       False,
            "underline":    False,
            "color":        rules.get("bullet_color",          "#000000"),
            "alignment":    "left",
            "line_spacing": rules.get("bullet_line_spacing",   1.0),
            "space_before": rules.get("bullet_space_before",   0.0),
            "space_after":  rules.get("bullet_space_after",    6.0),
            "indent_left":  rules.get("bullet_indent",         0.5),
        }

    def _toc_style(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        TOC entries share body font but are not justified — they use
        left alignment with dot leaders handled by the frontend.
        """
        return {
            "font_name":    rules.get("body_font",     "Times New Roman"),
            "font_size":    rules.get("body_size",     11),
            "bold":         False,
            "italic":       False,
            "underline":    False,
            "color":        rules.get("body_color",    "#000000"),
            "alignment":    "left",
            "line_spacing": 1.0,
            "space_before": 2.0,
            "space_after":  2.0,
            "indent_left":  0.0,
        }

    def _formula_style(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formulas are centre-aligned, use a monospace/serif font,
        with extra vertical breathing room.
        """
        return {
            "font_name":    rules.get("formula_font",  "Courier New"),
            "font_size":    rules.get("formula_size",  11),
            "bold":         False,
            "italic":       True,      # convention for inline formulas
            "underline":    False,
            "color":        rules.get("formula_color", "#000000"),
            "alignment":    "center",
            "line_spacing": 1.0,
            "space_before": 6.0,
            "space_after":  6.0,
            "indent_left":  0.0,
        }

    def _figure_style(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "font_name":    rules.get("figure_font", "Times New Roman"),
            "font_size":    rules.get("figure_size", 11),
            "bold":         False,
            "italic":       False,
            "underline":    False,
            "color":        rules.get("figure_color", "#000000"),
            "alignment":    "center",
            "line_spacing": rules.get("figure_line_spacing", 1.0),
            "space_before": rules.get("figure_space_before", 6.0),
            "space_after":  rules.get("figure_space_after", 6.0),
            "indent_left":  0.0,
        }

    def _caption_style(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "font_name":    rules.get("caption_font", "Times New Roman"),
            "font_size":    rules.get("caption_size", 10),
            "bold":         False,
            "italic":       True,
            "underline":    False,
            "color":        rules.get("caption_color", "#000000"),
            "alignment":    "center",
            "line_spacing": rules.get("caption_line_spacing", 1.0),
            "space_before": rules.get("caption_space_before", 2.0),
            "space_after":  rules.get("caption_space_after", 6.0),
            "indent_left":  0.0,
        }

    def _reference_style(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "font_name":    rules.get("reference_font", rules.get("body_font", "Times New Roman")),
            "font_size":    rules.get("reference_size", rules.get("body_size", 11)),
            "bold":         False,
            "italic":       False,
            "underline":    False,
            "color":        rules.get("reference_color", "#000000"),
            "alignment":    "left",
            "line_spacing": rules.get("reference_line_spacing", 1.0),
            "space_before": rules.get("reference_space_before", 0.0),
            "space_after":  rules.get("reference_space_after", 4.0),
            "indent_left":  rules.get("reference_indent_left", 0.25),
        }

    # ── Spacing conversion ────────────────────────────────────────────────────

    @staticmethod
    def _convert_spacing_value(value: Any, rules: Dict[str, Any]) -> float:
        """
        Convert spacing value based on the spacing_unit setting.
        Returns value in a standardized format (points).
        """
        try:
            unit = rules.get("spacing_unit", "mm")
            numeric_value = float(value) if value else 0.0
            
            # Values are already converted to points in templates.py
            # Just return the numeric value
            return numeric_value
        except (ValueError, TypeError):
            return 0.0

    # ── Defaults ──────────────────────────────────────────────────────────────

    @staticmethod
    def _default_heading_size(level: int) -> int:
        return {1: 16, 2: 14, 3: 13, 4: 12}.get(level, 12)

    @staticmethod
    def _default_space_before(level: int) -> float:
        return {1: 12.0, 2: 10.0, 3: 8.0, 4: 6.0}.get(level, 6.0)

    @staticmethod
    def _default_space_after(level: int) -> float:
        return {1: 6.0, 2: 5.0, 3: 4.0, 4: 3.0}.get(level, 3.0)

    def _default_rules(self) -> Dict[str, Any]:
        """Built-in fallback — mirrors paragraph_formatter._get_default_rules()."""
        return {
            "spacing_unit": "mm",  # NEW: Default unit for spacing values
            
            "heading1_font": "Times New Roman", "heading1_size": 16,
            "heading1_bold": True, "heading1_italic": False,  "heading1_line_spacing": 1.5,
            "heading1_space_before": 12.0, "heading1_space_after": 6.0,

            "heading2_font": "Times New Roman", "heading2_size": 14,
            "heading2_bold": True, "heading2_italic": False,  "heading2_line_spacing": 1.5,
            "heading2_space_before": 10.0, "heading2_space_after": 5.0,

            "heading3_font": "Times New Roman", "heading3_size": 13,
            "heading3_bold": True, "heading3_italic": False,  "heading3_line_spacing": 1.5,
            "heading3_space_before": 8.0, "heading3_space_after": 4.0,

            "heading4_font": "Times New Roman", "heading4_size": 12,
            "heading4_bold": False, "heading4_italic": False, "heading4_line_spacing": 1.5,
            "heading4_space_before": 6.0, "heading4_space_after": 3.0,

            "body_font": "Times New Roman", "body_size": 11,
            "body_line_spacing": 1.0, "body_space_before": 0.0,
            "body_space_after": 6.0,

            "bullet_font": "Times New Roman", "bullet_size": 12,
            "bullet_indent": 0.5, "bullet_line_spacing": 1.0,
            "bullet_space_before": 0.0, "bullet_space_after": 6.0,
        }

    def _merge_with_defaults(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start from built-in defaults and overlay with template values,
        skipping None values (preserves user intent).
        """
        merged = self._default_rules()
        for k, v in rules.items():
            if v is not None:
                merged[k] = v
        return merged


# ── Singleton ─────────────────────────────────────────────────────────────────
smart_formatter = SmartFormatter()
