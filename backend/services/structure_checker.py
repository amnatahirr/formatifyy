"""
Layer 3 — Structure Checker
=============================
Reads the template's required_sections list and the document's heading
blocks (from Layer 1 + Layer 2) and produces a detailed structure report:

    ✓ Missing sections        — required but not found at all
    ✓ Wrong order             — found but in wrong position
    ✓ Empty sections          — heading exists but no content follows
    ✓ Paragraph before first heading — content before any heading
    ✓ Extra headings          — in document but not in template

Input
------
    template_sections : list of dicts from DB
        [{"name": "Introduction", "order": 1, "required": true}, ...]

    blocks : list of Layer-1 block dicts
        [{"type": "heading"|"paragraph"|..., "text": "...", ...}, ...]

Output (StructureReport)
------------------------
    {
        "status": "pass" | "fail",
        "score":  85,           # 0-100
        "issues": [
            {"severity": "error"|"warning"|"info",
             "code":     "MISSING_SECTION"|"WRONG_ORDER"|"EMPTY_SECTION"
                         |"CONTENT_BEFORE_HEADING"|"EXTRA_HEADING",
             "message":  "...",
             "details":  {...}},
            ...
        ],
        "section_results": [
            {"name": "Introduction", "order": 1, "required": true,
             "status": "found"|"missing"|"wrong_order"|"empty",
             "matched_heading": "Intro",
             "match_layer": "synonym",
             "document_position": 2},
            ...
        ],
        "summary": {
            "total_required": 8,
            "found": 6,
            "missing": 1,
            "wrong_order": 1,
            "empty": 0,
            "extra_headings": 2,
            "content_before_heading": false
        }
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from services.heading_normalizer import HeadingNormalizer, MatchResult


# ─────────────────────────────────────────────────────────────────────────────
# Issue codes & severity
# ─────────────────────────────────────────────────────────────────────────────

class Code:
    MISSING_SECTION          = "MISSING_SECTION"
    WRONG_ORDER              = "WRONG_ORDER"
    EMPTY_SECTION            = "EMPTY_SECTION"
    CONTENT_BEFORE_HEADING   = "CONTENT_BEFORE_HEADING"
    EXTRA_HEADING            = "EXTRA_HEADING"
    OPTIONAL_MISSING         = "OPTIONAL_MISSING"


class Severity:
    ERROR   = "error"     # required section problem
    WARNING = "warning"   # optional / order / empty
    INFO    = "info"      # extra headings


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str
    code:     str
    message:  str
    details:  Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionResult:
    name:              str
    order:             int        # expected order from template (1-based)
    required:          bool
    status:            str        # "found" | "missing" | "wrong_order" | "empty"
    matched_heading:   Optional[str] = None
    match_layer:       Optional[str] = None
    document_position: Optional[int] = None   # 1-based position in doc headings
    paragraph_index:   Optional[int] = None   # block index (for frontend navigation)


@dataclass
class StructureReport:
    status:          str                    # "pass" | "fail"
    score:           int                    # 0–100
    issues:          List[Issue]
    section_results: List[SectionResult]
    summary:         Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "score":  self.score,
            "issues": [
                {
                    "severity": i.severity,
                    "code":     i.code,
                    "message":  i.message,
                    "details":  i.details,
                }
                for i in self.issues
            ],
            "section_results": [
                {
                    "name":              r.name,
                    "order":             r.order,
                    "required":          r.required,
                    "status":            r.status,
                    "matched_heading":   r.matched_heading,
                    "match_layer":       r.match_layer,
                    "document_position": r.document_position,
                    "paragraph_index":   r.paragraph_index,
                }
                for r in self.section_results
            ],
            "summary": self.summary,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main checker
# ─────────────────────────────────────────────────────────────────────────────

class StructureChecker:
    """
    Parameters
    ----------
    fuzzy_threshold    : passed to HeadingNormalizer (Layer 2)
    semantic_threshold : passed to HeadingNormalizer (Layer 2)
    use_semantic       : set False on low-end machines
    """

    def __init__(
        self,
        fuzzy_threshold: float    = 80.0,
        semantic_threshold: float = 0.35,   # matches HeadingNormalizer default
        use_semantic: bool        = True,
    ):
        self._normalizer = HeadingNormalizer(
            fuzzy_threshold    = fuzzy_threshold,
            semantic_threshold = semantic_threshold,
            use_semantic       = use_semantic,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def check(
        self,
        blocks:            List[Dict[str, Any]],
        template_sections: List[Dict[str, Any]],
    ) -> StructureReport:
        """
        Run the full Layer 3 structure check.

        Parameters
        ----------
        blocks            : Layer-1 output from document_block_extractor.extract_blocks()
        template_sections : required_sections list from the template DB record
                            [{"name": "...", "order": N, "required": bool}, ...]
        """
        if not template_sections:
            return self._empty_template_report(blocks)

        # Sort template sections by their defined order
        sorted_template = sorted(template_sections, key=lambda s: s.get("order", 999))

        # ── Extract heading texts in document order ───────────────────────────
        heading_blocks = [b for b in blocks if b.get("type") == "heading"]

        # Fallback: if heading extraction is broken upstream, infer headings
        # using the SAME heuristics BulletCheck uses (style + text signals).
        if not heading_blocks:
            import re as _re

            _NUM_H = _re.compile(r"^\d+[.)]\s+[A-Z]")

            def _is_heading_like(b: Dict[str, Any]) -> bool:
                text = (b.get("text") or "").strip()
                if not text:
                    return False
                style_name = str(b.get("style") or "").lower()
                if "heading" in style_name:
                    return True
                if _NUM_H.match(text):
                    return True
                wc = len(text.split())
                if text.isupper() and 1 <= wc <= 8:
                    return True
                if style_name == "normal":
                    is_bold = bool(b.get("is_bold"))
                    ends_p = text.endswith((".", "?", "!"))
                    if is_bold and wc <= 10 and not ends_p:
                        return True
                return False

            heading_blocks = [b for b in blocks if _is_heading_like(b)]

        heading_texts  = [str(h.get("text", "")) for h in heading_blocks if str(h.get("text", "")).strip()]

        # Build a lookup: heading_text → block index (for paragraph_index output)
        heading_block_index: Dict[str, int] = {
            str(h.get("text", "")).strip(): h.get("index", -1)
            for h in heading_blocks
            if str(h.get("text", "")).strip()
        }

        # ── Layer 2: match headings → required sections ───────────────────────
        required_names = [s["name"] for s in sorted_template]
        l2_report = self._normalizer.match_headings(heading_texts, required_names)

        # Build a lookup: required_name → MatchResult
        match_lookup: Dict[str, MatchResult] = {
            m.required: m for m in l2_report.matches
        }

        # Build a lookup: matched_heading_text → position in document (1-based)
        heading_position: Dict[str, int] = {
            text: idx + 1 for idx, text in enumerate(heading_texts)
        }

        issues:          List[Issue]         = []
        section_results: List[SectionResult] = []

        # ── Check 1: Content before first heading ─────────────────────────────
        content_before = self._check_content_before_heading(blocks)
        if content_before:
            issues.append(Issue(
                severity = Severity.WARNING,
                code     = Code.CONTENT_BEFORE_HEADING,
                message  = "Document contains content before the first heading.",
                details  = {"text_preview": content_before[:120]},
            ))

        # ── Check 2: Per-section analysis ────────────────────────────────────
        # We need to detect order violations, so track the last seen doc position
        last_doc_position = 0

        for template_sec in sorted_template:
            sec_name   = template_sec["name"]
            sec_order  = template_sec.get("order", 0)
            sec_req    = template_sec.get("required", True)
            match      = match_lookup.get(sec_name)

            if match is None or match.status == "missing":
                # Section not found at all
                status = "missing"
                sr = SectionResult(
                    name     = sec_name,
                    order    = sec_order,
                    required = sec_req,
                    status   = status,
                )
                if sec_req:
                    issues.append(Issue(
                        severity = Severity.ERROR,
                        code     = Code.MISSING_SECTION,
                        message  = f'Required section "{sec_name}" is missing from the document.',
                        details  = {"section": sec_name, "expected_order": sec_order},
                    ))
                else:
                    issues.append(Issue(
                        severity = Severity.INFO,
                        code     = Code.OPTIONAL_MISSING,
                        message  = f'Optional section "{sec_name}" is not present.',
                        details  = {"section": sec_name},
                    ))
                section_results.append(sr)
                continue

            # Section was found — get its doc position
            matched_text = match.matched_heading
            doc_pos      = heading_position.get(matched_text, 0)

            # ── Check empty section ───────────────────────────────────────────
            is_empty = self._is_section_empty(blocks, matched_text)
            if is_empty:
                issues.append(Issue(
                    severity = Severity.WARNING,
                    code     = Code.EMPTY_SECTION,
                    message  = f'Section "{sec_name}" has no content after its heading.',
                    details  = {"section": sec_name, "heading": matched_text},
                ))

            # ── Check order ───────────────────────────────────────────────────
            order_ok = doc_pos >= last_doc_position
            if not order_ok:
                issues.append(Issue(
                    severity = Severity.ERROR,
                    code     = Code.WRONG_ORDER,
                    message  = (
                        f'Section "{sec_name}" appears too early in the document. '
                        f'Expected after position {last_doc_position}, '
                        f'found at position {doc_pos}.'
                    ),
                    details  = {
                        "section":           sec_name,
                        "expected_after_pos": last_doc_position,
                        "found_at_pos":       doc_pos,
                    },
                ))

            if doc_pos > 0:
                last_doc_position = doc_pos

            section_results.append(SectionResult(
                name              = sec_name,
                order             = sec_order,
                required          = sec_req,
                status            = "empty"       if is_empty
                                    else "wrong_order" if not order_ok
                                    else "found",
                matched_heading   = matched_text,
                match_layer       = match.match_layer,
                document_position = doc_pos,
                paragraph_index   = heading_block_index.get(matched_text or "", None),
            ))

        # ── Check 3: Extra headings ───────────────────────────────────────────
        for extra in l2_report.extra_headings:
            issues.append(Issue(
                severity = Severity.INFO,
                code     = Code.EXTRA_HEADING,
                message  = f'Heading "{extra}" is not in the template\'s required sections.',
                details  = {"heading": extra},
            ))

        # ── Score ─────────────────────────────────────────────────────────────
        score = self._compute_score(section_results, issues)

        # ── Summary ───────────────────────────────────────────────────────────
        summary = {
            "total_required":          sum(1 for s in sorted_template if s.get("required", True)),
            "total_sections":          len(sorted_template),
            "found":                   sum(1 for r in section_results if r.status == "found"),
            "missing":                 sum(1 for r in section_results if r.status == "missing" and r.required),
            "wrong_order":             sum(1 for r in section_results if r.status == "wrong_order"),
            "empty":                   sum(1 for r in section_results if r.status == "empty"),
            "optional_missing":        sum(1 for r in section_results if r.status == "missing" and not r.required),
            "extra_headings":          len(l2_report.extra_headings),
            "content_before_heading":  content_before is not None,
        }

        # Pass = no errors (warnings are ok)
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return StructureReport(
            status          = "fail" if has_errors else "pass",
            score           = score,
            issues          = issues,
            section_results = section_results,
            summary         = summary,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _check_content_before_heading(
        self, blocks: List[Dict]
    ) -> Optional[str]:
        """
        Return the text of the first paragraph that appears before any heading,
        or None if the document starts correctly with a heading.
        """
        for block in blocks:
            if block["type"] == "heading":
                return None   # first non-empty block is a heading — good
            if block["type"] == "paragraph" and block["text"].strip():
                return block["text"]
        return None

    def _is_section_empty(
        self, blocks: List[Dict], heading_text: str
    ) -> bool:
        """
        Return True if the heading is followed immediately by another heading
        or by the end of the document (i.e. no paragraph/list content).
        """
        found = False
        for block in blocks:
            if not found:
                if block["type"] == "heading" and block["text"] == heading_text:
                    found = True
                continue
            # After the heading
            if block["type"] == "heading":
                return True   # next block is another heading — empty section
            if block["type"] in ("paragraph", "list_item", "table"):
                return False  # has content
        return found   # heading at very end of doc with nothing after

    def _compute_score(
        self,
        results: List[SectionResult],
        issues:  List[Issue],
    ) -> int:
        """
        Score from 0–100.

        Deductions:
          • Each missing required section : -15 pts
          • Each wrong-order section      : -10 pts
          • Each empty section            : -5  pts
          • Content before heading        : -5  pts
        """
        score = 100
        for r in results:
            if r.status == "missing" and r.required:
                score -= 15
            elif r.status == "wrong_order":
                score -= 10
            elif r.status == "empty":
                score -= 5

        for i in issues:
            if i.code == Code.CONTENT_BEFORE_HEADING:
                score -= 5

        return max(0, min(100, score))

    def _empty_template_report(self, blocks: List[Dict]) -> StructureReport:
        """Return a neutral report when the template has no required sections defined."""
        heading_texts = [b["text"] for b in blocks if b["type"] == "heading"]
        return StructureReport(
            status = "pass",
            score  = 100,
            issues = [Issue(
                severity = Severity.INFO,
                code     = Code.EXTRA_HEADING,
                message  = "Template has no required sections defined. "
                           "Structure check skipped.",
                details  = {},
            )],
            section_results = [],
            summary = {
                "total_required": 0,
                "total_sections": 0,
                "found": 0,
                "missing": 0,
                "wrong_order": 0,
                "empty": 0,
                "optional_missing": 0,
                "extra_headings": len(heading_texts),
                "content_before_heading": False,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function (used by router)
# ─────────────────────────────────────────────────────────────────────────────

def check_structure(
    blocks:            List[Dict[str, Any]],
    template_sections: List[Dict[str, Any]],
    use_semantic:      bool  = True,
) -> Dict[str, Any]:
    """Thin JSON-serialisable wrapper. Call this from routers."""
    checker = StructureChecker(use_semantic=use_semantic)
    report  = checker.check(blocks, template_sections)
    return report.to_dict()