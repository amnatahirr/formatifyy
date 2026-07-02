"""Transformer heading-level classifier with heuristic fallback."""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional
from services.ai_element_classifier import ai_element_classifier, HEADING_LABELS


# ── Regex patterns ────────────────────────────────────────────────────────────

# Explicit numbering schemes
_RE_H1 = re.compile(
    r"^(\d+)\.\s+\S"                    # "1. Introduction"
    r"|^chapter\s+\d+"                  # "Chapter 3"
    r"|^part\s+\d+"                     # "Part II"
    r"|^appendix\s+[a-z\d]",            # "Appendix A"
    re.IGNORECASE,
)
_RE_H2 = re.compile(
    r"^(\d+)\.(\d+)\s+\S"              # "1.1 Background"
    r"|^section\s+\d+\.\d+",           # "Section 2.3"
    re.IGNORECASE,
)
_RE_H3 = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)\s+\S"      # "1.1.1 Detail"
)
_RE_H4 = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)\.(\d+)\s+\S"  # "1.1.1.1 Deep"
)

# Keywords that strongly suggest a particular level
_H1_KEYWORDS = frozenset(
    ["introduction", "conclusion", "abstract", "references",
     "bibliography", "methodology", "background", "overview",
     "summary", "appendix", "acknowledgements", "results",
     "discussion", "literature review", "implementation"]
)

_H2_KEYWORDS = frozenset(
    ["related work", "problem statement", "research questions",
     "objectives", "scope", "limitations", "future work",
     "evaluation", "testing", "analysis", "design", "architecture",
     "system design", "data collection", "experimental setup"]
)

# Typical heading font sizes → level mapping (used when metadata available)
_FONT_SIZE_MAP = [
    (17, 1),  # ≥ 17pt → H1
    (15, 2),  # ≥ 15pt → H2
    (13, 3),  # ≥ 13pt → H3
    (0,  4),  # anything smaller → H4
]


class HeadingClassifier:
    """Refines heading blocks to H1/H2/H3 with confidence and fallback."""

    def classify(
        self,
        blocks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Parameters
        ----------
        blocks : list
            Output of ContentDetector. Each dict has at minimum
            ``{"type": str, "raw_text": str}``.

        Returns
        -------
        Same list, heading dicts now carry ``"level": int`` (1–4).
        """
        for block in blocks:
            if block.get("type") != "heading":
                continue
            text = str(block.get("raw_text", "")).strip()
            ai_pred = ai_element_classifier.predict(text, labels=HEADING_LABELS, threshold=0.58)
            ai_label = str(ai_pred["label"])
            ai_conf = float(ai_pred["confidence"])
            level = self._label_to_level(ai_label)
            if level is None:
                level = self._heuristic_heading_level(text, block.get("font_size"))
            block["level"] = level
            block["heading_confidence"] = round(ai_conf, 3)
            block["ai_heading_label"] = ai_label

        return blocks

    @staticmethod
    def _label_to_level(label: str) -> Optional[int]:
        if label == "heading_h1":
            return 1
        if label == "heading_h2":
            return 2
        if label == "heading_h3":
            return 3
        return None

    def _heuristic_heading_level(self, text: str, font_size: Optional[float]) -> int:
        if _RE_H4.match(text):
            return 3
        if _RE_H3.match(text):
            return 3
        if _RE_H2.match(text):
            return 2
        if _RE_H1.match(text):
            return 1
        if font_size is not None:
            for threshold, lvl in _FONT_SIZE_MAP:
                if font_size >= threshold:
                    return min(lvl, 3)
        lower = text.lower().strip()
        if any(kw in lower for kw in _H1_KEYWORDS):
            return 1
        if any(kw in lower for kw in _H2_KEYWORDS):
            return 2
        return 2


heading_classifier = HeadingClassifier()
