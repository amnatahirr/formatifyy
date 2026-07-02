"""
checker/style_checker.py
Layer 3 – Styling / Formatting Check
Reads actual docx paragraph styles and compares them to template rules.
Returns issues in the same format as structure_checker and content_checker.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Default template rules (used when no template_rules are passed in) ──────
DEFAULT_RULES: Dict[str, Any] = {
    "heading1": {"size": 16, "bold": True,  "font": None},
    "heading2": {"size": 14, "bold": True,  "font": None},
    "heading3": {"size": 12, "bold": True,  "font": None},
    "body":     {"size": 12, "bold": False, "font": "Times New Roman"},
    "line_spacing": 1.5,
    "tolerance_pt": 1.0,    # ±1pt tolerance to avoid false positives
}

# How python-docx style names map to our rule keys
STYLE_NAME_MAP = {
    "heading 1": "heading1",
    "heading 2": "heading2",
    "heading 3": "heading3",
    "normal":    "body",
    "default paragraph font": "body",
}

# Don't report issues on very short runs (e.g. punctuation-only)
MIN_TEXT_LENGTH = 3


class StyleChecker:
    """
    Checks docx document styling against template rules.

    Usage:
        checker = StyleChecker()
        issues  = checker.check(docx_path, template_rules=None)

    `template_rules` can be None (uses defaults) or the dict from
    templates.formatting_rules in your database.

    Returns a list of issue dicts:
        [{
            "type":      "wrong_font_size",
            "severity":  "warning",
            "code":      "STYLE_FONT_SIZE",
            "message":   "Heading 'Introduction' is 14pt, expected 16pt",
            "paragraph": "Introduction",
        }, ...]
    """

    def check(
        self,
        docx_path: str,
        template_rules: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        if not os.path.exists(docx_path):
            logger.warning("[StyleChecker] File not found: %s", docx_path)
            return []

        ext = os.path.splitext(docx_path)[1].lower()
        if ext != ".docx":
            # PDF and TXT styling can't be read with python-docx – skip gracefully
            return []

        try:
            from docx import Document
            from docx.shared import Pt
        except ImportError:
            logger.error("[StyleChecker] python-docx not installed.")
            return []

        rules = self._merge_rules(template_rules)
        issues: List[Dict[str, Any]] = []
        seen_issues: set = set()   # deduplicate identical messages

        try:
            doc = Document(docx_path)
        except Exception as e:
            logger.error("[StyleChecker] Cannot open docx: %s", e)
            return []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text or len(text) < MIN_TEXT_LENGTH:
                continue

            style_key = self._resolve_style(para.style.name)
            rule      = rules.get(style_key)
            if rule is None:
                continue

            # ── Check each run inside the paragraph ───────────────────────
            for run in para.runs:
                run_text = run.text.strip()
                if not run_text:
                    continue

                # Font size
                if run.font.size is not None:
                    actual_pt = run.font.size.pt
                    expected  = rule.get("size")
                    tolerance = rules.get("tolerance_pt", 1.0)

                    if expected and abs(actual_pt - expected) > tolerance:
                        msg = (
                            f"'{text[:50]}' has {actual_pt:.0f}pt font, "
                            f"expected {expected}pt ({para.style.name})"
                        )
                        key = ("font_size", text[:50], actual_pt)
                        if key not in seen_issues:
                            seen_issues.add(key)
                            issues.append({
                                "type":      "wrong_font_size",
                                "severity":  "warning",
                                "code":      "STYLE_FONT_SIZE",
                                "message":   msg,
                                "paragraph": text[:80],
                            })

                # Bold
                expected_bold = rule.get("bold")
                if expected_bold is not None and run.bold is not None:
                    if run.bold != expected_bold:
                        expected_label = "bold" if expected_bold else "not bold"
                        msg = (
                            f"'{text[:50]}' should be {expected_label} "
                            f"({para.style.name})"
                        )
                        key = ("bold", text[:50], run.bold)
                        if key not in seen_issues:
                            seen_issues.add(key)
                            issues.append({
                                "type":      "wrong_bold",
                                "severity":  "warning",
                                "code":      "STYLE_BOLD",
                                "message":   msg,
                                "paragraph": text[:80],
                            })

                # Font name
                expected_font = rule.get("font")
                if expected_font and run.font.name:
                    if run.font.name.lower() != expected_font.lower():
                        msg = (
                            f"'{text[:50]}' uses '{run.font.name}', "
                            f"expected '{expected_font}'"
                        )
                        key = ("font_name", text[:50], run.font.name)
                        if key not in seen_issues:
                            seen_issues.add(key)
                            issues.append({
                                "type":      "wrong_font",
                                "severity":  "warning",
                                "code":      "STYLE_FONT_NAME",
                                "message":   msg,
                                "paragraph": text[:80],
                            })

            # ── Line spacing (paragraph level) ────────────────────────────
            expected_spacing = rules.get("line_spacing")
            if expected_spacing and para.paragraph_format.line_spacing:
                actual_spacing = para.paragraph_format.line_spacing
                # line_spacing can be a Pt value or a float multiplier
                try:
                    # If it's a Length object, convert
                    actual_val = float(actual_spacing)
                    # Heuristic: if > 10 it's in EMUs, convert to lines
                    if actual_val > 10:
                        actual_val = actual_val / 240_000

                    if abs(actual_val - expected_spacing) > 0.1:
                        msg = (
                            f"'{text[:50]}' line spacing is {actual_val:.1f}, "
                            f"expected {expected_spacing}"
                        )
                        key = ("line_spacing", text[:50])
                        if key not in seen_issues:
                            seen_issues.add(key)
                            issues.append({
                                "type":      "wrong_line_spacing",
                                "severity":  "warning",
                                "code":      "STYLE_LINE_SPACING",
                                "message":   msg,
                                "paragraph": text[:80],
                            })
                except (TypeError, ValueError):
                    pass

        logger.info("[StyleChecker] Found %d style issues in %s",
                    len(issues), os.path.basename(docx_path))
        return issues

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _resolve_style(self, style_name: str) -> Optional[str]:
        """Map python-docx style name → our rule key."""
        return STYLE_NAME_MAP.get(style_name.lower().strip())

    def _merge_rules(
        self, template_rules: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge template_rules from DB into our rule structure.
        template_rules can contain keys like:
            heading1_size, heading1_bold, body_font, body_size, line_spacing
        """
        rules = {k: dict(v) if isinstance(v, dict) else v
                 for k, v in DEFAULT_RULES.items()}

        if not template_rules:
            return rules

        # Map flat template keys → nested rule structure
        mapping = {
            "heading1_size":    ("heading1", "size"),
            "heading1_bold":    ("heading1", "bold"),
            "heading1_font":    ("heading1", "font"),
            "heading2_size":    ("heading2", "size"),
            "heading2_bold":    ("heading2", "bold"),
            "heading2_font":    ("heading2", "font"),
            "body_size":        ("body", "size"),
            "body_bold":        ("body", "bold"),
            "body_font":        ("body", "font"),
            "line_spacing":     (None, "line_spacing"),
            "tolerance_pt":     (None, "tolerance_pt"),
        }

        for tpl_key, (section, field) in mapping.items():
            if tpl_key in template_rules:
                val = template_rules[tpl_key]
                if section is None:
                    rules[field] = val
                else:
                    if isinstance(rules.get(section), dict):
                        rules[section][field] = val

        return rules