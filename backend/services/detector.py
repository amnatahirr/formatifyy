"""Transformer-based element detection with heuristic fallback."""

from __future__ import annotations

import re
from typing import List, Dict, Any
from services.ai_element_classifier import ai_element_classifier, LABELS

# Kept for cheap rule-based short-circuiting
_RE_FORMULA = re.compile(
    r"\$.*?\$|\\\(|\\\[|\\frac|\\sum|\\int|\\sqrt|[∑∫√∂∇±×÷≤≥≠αβγδεθλμπσφψω]"
)
_RE_BULLET   = re.compile(r"^\s*[-•*]\s+")
_RE_NUMBERED = re.compile(r"^\s*(\d+|[a-zA-Z])[\)\.]\s+")


class ContentDetector:
    """Runs transformer element detection per block/line."""

    def detect(self, raw_text: str) -> List[Dict[str, Any]]:
        lines = self._split_lines(raw_text)
        blocks = []
        for idx, line in enumerate(lines):
            text = line.strip()
            if not text:
                continue
            blocks.append(self._classify_text(text, idx))
        return blocks

    def detect_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched = []
        for idx, b in enumerate(blocks):
            text = b.get("text", "").strip()
            if not text:
                continue

            existing_type = b.get("type", "paragraph")
            if existing_type in ("table", "figure", "caption", "reference"):
                detected = self._make_block(text, idx, existing_type, 0.96, ai_label=existing_type)
            elif existing_type == "heading":
                lvl = int(b.get("level") or 1)
                ai_label = {1: "heading_h1", 2: "heading_h2", 3: "heading_h3"}.get(min(lvl, 3), "heading_h3")
                detected = self._make_block(text, idx, "heading", 0.95, level=lvl, ai_label=ai_label)
            elif existing_type == "list_item":
                detected = self._make_block(text, idx, "paragraph", 0.75, ai_label="paragraph")
            else:
                detected = self._classify_text(text, idx)
            detected["original"] = b
            enriched.append(detected)
        return enriched

    def _split_lines(self, raw_text: str) -> List[str]:
        lines = raw_text.splitlines()
        merged: List[str] = []
        carry = ""

        for line in lines:
            stripped = line.rstrip()
            if stripped.endswith("-") and len(stripped) > 2:
                carry += stripped[:-1]
            else:
                merged.append(carry + stripped)
                carry = ""

        if carry:
            merged.append(carry)
        return merged

    def _classify_text(self, text: str, idx: int) -> Dict[str, Any]:
        # keep tiny deterministic checks for obvious structural tokens
        if _RE_FORMULA.search(text):
            return self._make_block(text, idx, "formula", 0.95, ai_label="formula")
        if _RE_BULLET.match(text) or _RE_NUMBERED.match(text):
            return self._make_block(text, idx, "paragraph", 0.70, ai_label="paragraph")

        pred = ai_element_classifier.predict(text, labels=LABELS, threshold=0.60)
        label = str(pred["label"])
        conf = float(pred["confidence"])

        if label.startswith("heading_h"):
            level = int(label.split("_h")[-1])
            return self._make_block(text, idx, "heading", conf, level=level, ai_label=label)
        if label in ("table", "figure", "caption", "reference"):
            return self._make_block(text, idx, label, conf, ai_label=label)
        return self._make_block(text, idx, "paragraph", conf, ai_label=label)

    @staticmethod
    def _make_block(
        text:       str,
        index:      int,
        block_type: str,
        confidence: float,
        level: int | None = None,
        ai_label: str | None = None,
    ) -> Dict[str, Any]:
        block = {
            "index":      index,
            "raw_text":   text,
            "type":       block_type,
            "confidence": round(confidence, 3),
        }
        if level is not None:
            block["level"] = level
        if ai_label is not None:
            block["ai_label"] = ai_label
        return block


content_detector = ContentDetector()
