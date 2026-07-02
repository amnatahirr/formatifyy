import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class BulletCandidate:
    index: int
    text: str
    confidence: float
    reason: str


class BulletSequenceDetector:
    """
    Hybrid detector:
      1) feature scoring per block
      2) sequence grouping (B/I/O-like continuation)
      3) confidence-gated list groups
    """

    def __init__(self) -> None:
        self._num_heading = re.compile(r"^\d+(\.\d+)*[.)]?\s+[A-Z]")
        self._num_marker = re.compile(r"^\s*\(?\d+[.)]\s+\S")
        self._alpha_marker = re.compile(r"^\s*\(?[A-Za-z][.)]\s+\S")
        self._roman_marker = re.compile(r"^\s*\(?[ivxlcdmIVXLCDM]+[.)]\s+\S")
        self._label = re.compile(r"^[A-Za-z][A-Za-z0-9 ,/\-\(\)\.]{1,60}[:\-]\s+\S")
        self._step = re.compile(
            r"^(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
            r"final|last|next|then|another)\s+(step|item|point|stage|phase|task)",
            re.IGNORECASE,
        )
        self._caption = re.compile(
            r"^(fig(?:ure)?|table|chart|diagram|appendix)[\.\s]*\d*\s*[:\-–]",
            re.IGNORECASE,
        )
        self._tof = re.compile(
            r"^(note\s*:|table of figures|list of figures|references)",
            re.IGNORECASE,
        )
        self._bullet_chars = ("•", "○", "■", "-", "*", "→", "»", "▪", "–")
        self._small = {"a", "an", "the", "in", "of", "for", "and", "or", "but", "to", "with", "by"}
        self._ctx = (
            "following",
            "below",
            "includes",
            "consists of",
            "contains",
            "such as",
            "examples",
            "list",
            "steps",
            "requirements",
            "features",
            "benefits",
            "as follows",
            "are:",
        )

    def detect_groups(self, blocks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        filtered = self._normalize_blocks(blocks)
        groups = self._scan_heading_sections(filtered)
        groups = self._scan_colon_intros(filtered, groups)
        return groups

    def _normalize_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        norm: List[Dict[str, Any]] = []
        for i, b in enumerate(blocks):
            text = (b.get("text") or "").strip()
            if not text:
                continue
            norm.append(
                {
                    "index": int(b.get("index", i)),
                    "text": text,
                    "type": b.get("type", "paragraph"),
                    "metadata": b.get("metadata", {}),
                }
            )
        return norm

    def _is_heading(self, block: Dict[str, Any]) -> bool:
        text = block["text"]
        if block.get("type") == "heading":
            return True
        if self._num_heading.match(text):
            return True
        if text.isupper() and len(text.split()) <= 8:
            return True
        words = text.split()
        return (
            len(words) <= 6
            and not text.endswith((".", "?", "!", ":"))
            and all(w and (w[0].isupper() or w.lower() in self._small) for w in words)
        )

    def _is_caption_or_tof(self, text: str) -> bool:
        tl = text.lower().strip()
        if self._caption.match(text) or self._tof.match(text):
            return True
        if tl.startswith("description automatically generated"):
            return True
        return text.rstrip().endswith("—")

    def _score(self, text: str, prev_text: str, heading_text: str) -> Tuple[float, str]:
        if not text or self._is_caption_or_tof(text):
            return 0.0, "filtered"
        if self._num_heading.match(text):
            return 0.0, "heading_like"

        words = len(text.split())
        ends_sentence = text.endswith((".", "?", "!"))
        score = 0.0
        reasons = []

        if text.startswith(self._bullet_chars):
            score += 0.95
            reasons.append("bullet_char")
        if self._num_marker.match(text) or self._alpha_marker.match(text) or self._roman_marker.match(text):
            score += 0.9
            reasons.append("enumeration_marker")
        if self._label.match(text):
            score += 0.7
            reasons.append("label_prefix")
        if self._step.match(text):
            score += 0.65
            reasons.append("step_phrase")

        hl = (heading_text or "").lower()
        pl = (prev_text or "").lower()
        if heading_text.rstrip().endswith(":"):
            score += 0.35
            reasons.append("heading_colon")
        if prev_text.rstrip().endswith(":"):
            score += 0.35
            reasons.append("intro_colon")
        if any(k in hl for k in self._ctx) or any(k in pl for k in self._ctx):
            score += 0.2
            reasons.append("list_context")

        if words <= 18:
            score += 0.2
            reasons.append("short_item")
        elif words > 45:
            score -= 0.35
            reasons.append("too_long")
        if ends_sentence and words > 28:
            score -= 0.2
            reasons.append("long_sentence")

        conf = max(0.0, min(1.0, score))
        reason = ",".join(reasons) if reasons else "weak"
        return conf, reason

    def _to_group(self, run: List[BulletCandidate]) -> List[Dict[str, Any]]:
        if len(run) < 2:
            return []
        avg = sum(it.confidence for it in run) / len(run)
        if avg < 0.42:
            return []
        return [
            {
                "text": it.text,
                "index": it.index,
                "confidence": round(it.confidence, 2),
                "reason": it.reason,
            }
            for it in run
        ]

    def _scan_heading_sections(self, blocks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        groups: List[List[Dict[str, Any]]] = []
        i = 0
        n = len(blocks)
        while i < n:
            b = blocks[i]
            if not self._is_heading(b):
                i += 1
                continue

            heading_text = b["text"]
            section: List[Dict[str, Any]] = []
            j = i + 1
            while j < n:
                nb = blocks[j]
                if self._is_heading(nb):
                    break
                if nb.get("type") != "list_item":
                    section.append(nb)
                j += 1

            run: List[BulletCandidate] = []
            for pos, item in enumerate(section):
                text = item["text"]
                prev = heading_text if pos == 0 else section[pos - 1]["text"]
                conf, reason = self._score(text, prev, heading_text)
                threshold = 0.35 if prev.rstrip().endswith(":") else 0.45
                if run and conf < threshold and len(text.split()) <= 12:
                    conf += 0.3
                    reason += ",continuation"
                if conf >= threshold:
                    run.append(BulletCandidate(item["index"], text, conf, reason))
                else:
                    g = self._to_group(run)
                    if g:
                        groups.append(g)
                    run = []
            g = self._to_group(run)
            if g:
                groups.append(g)
            i = j
        return groups

    def _scan_colon_intros(
        self,
        blocks: List[Dict[str, Any]],
        existing_groups: List[List[Dict[str, Any]]],
    ) -> List[List[Dict[str, Any]]]:
        used = {it["index"] for g in existing_groups for it in g}
        groups = list(existing_groups)
        i = 0
        n = len(blocks)
        while i < n:
            b = blocks[i]
            text = b["text"]
            if (
                not text.endswith(":")
                or b.get("type") == "list_item"
                or self._is_caption_or_tof(text)
                or b["index"] in used
            ):
                i += 1
                continue

            run: List[BulletCandidate] = []
            j = i + 1
            prev = text
            while j < n:
                nb = blocks[j]
                nt = nb["text"]
                if self._is_heading(nb):
                    break
                if nb.get("type") == "list_item" or self._is_caption_or_tof(nt) or nb["index"] in used:
                    prev = nt
                    j += 1
                    continue
                conf, reason = self._score(nt, prev, "")
                threshold = 0.35 if prev.rstrip().endswith(":") else 0.45
                if run and conf < threshold and len(nt.split()) <= 12:
                    conf += 0.3
                    reason += ",continuation"
                if conf >= threshold:
                    run.append(BulletCandidate(nb["index"], nt, conf, f"colon_intro:{reason}"))
                    prev = nt
                    j += 1
                    continue
                if run:
                    break
                prev = nt
                j += 1

            g = self._to_group(run)
            if g:
                groups.append(g)
                used.update(it["index"] for it in g)
            i = j
        return groups
