from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple, Optional

import spacy

try:
    from transformers import pipeline
except Exception:  # pragma: no cover - handled at runtime when dependency missing
    pipeline = None


LABELS = [
    "heading_h1",
    "heading_h2",
    "heading_h3",
    "paragraph",
    "table",
    "figure",
    "caption",
    "reference",
]

HEADING_LABELS = ["heading_h1", "heading_h2", "heading_h3"]

_RE_CAPTION = re.compile(r"^(figure|fig\.|table)\s*\d+[\.:]?\s+", re.IGNORECASE)
_RE_REFERENCE = re.compile(r"^\[\d+\]\s+|^\d+\.\s+[A-Z]", re.IGNORECASE)
_RE_H1 = re.compile(r"^(\d+)\.\s+\S|^chapter\s+\d+|^appendix\s+[a-z\d]", re.IGNORECASE)
_RE_H2 = re.compile(r"^(\d+)\.(\d+)\s+\S|^section\s+\d+\.\d+", re.IGNORECASE)
_RE_H3 = re.compile(r"^(\d+)\.(\d+)\.(\d+)\s+\S", re.IGNORECASE)


class AIElementClassifier:
    """
    Transformer-based element classifier with spaCy structural cues.
    Falls back to heuristics when confidence is low or model is unavailable.
    """

    def __init__(
        self,
        model_name: str = "facebook/bart-large-mnli",
        confidence_threshold: float = 0.60,
    ) -> None:
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self._pipe = None
        self._model_available = False
        self._nlp = self._load_spacy()

    def _load_spacy(self):
        try:
            return spacy.load("en_core_web_sm")
        except Exception:
            return spacy.blank("en")

    def preload(self) -> None:
        if self._pipe is not None:
            return
        if pipeline is None:
            self._model_available = False
            return
        try:
            device = 0 if os.getenv("CUDA_VISIBLE_DEVICES") else -1
            self._pipe = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=device,
            )
            self._model_available = True
        except Exception:
            self._pipe = None
            self._model_available = False

    def predict(
        self,
        text: str,
        labels: Optional[List[str]] = None,
        threshold: Optional[float] = None,
    ) -> Dict[str, object]:
        text = (text or "").strip()
        labels = labels or LABELS
        threshold = self.confidence_threshold if threshold is None else threshold

        if not text:
            return {"label": "paragraph", "confidence": 0.0, "fallback": True, "scores": {}}

        self.preload()
        cue_boost = self._spacy_cue_scores(text, labels)
        model_scores: Dict[str, float] = {l: 0.0 for l in labels}

        if self._model_available and self._pipe is not None:
            try:
                out = self._pipe(text, candidate_labels=labels, multi_label=False)
                model_scores = dict(zip(out["labels"], out["scores"]))
            except Exception:
                self._model_available = False

        # Blend model confidence with spaCy cue priors
        blended = {
            l: float(model_scores.get(l, 0.0) + cue_boost.get(l, 0.0))
            for l in labels
        }
        best_label = max(blended, key=blended.get)
        best_conf = min(blended[best_label], 1.0)

        if (not self._model_available) or (best_conf < threshold):
            h_label, h_conf = self._heuristic_label(text, labels)
            return {
                "label": h_label,
                "confidence": h_conf,
                "fallback": True,
                "scores": blended,
            }

        return {
            "label": best_label,
            "confidence": best_conf,
            "fallback": False,
            "scores": blended,
        }

    def _spacy_cue_scores(self, text: str, labels: List[str]) -> Dict[str, float]:
        cues = {l: 0.0 for l in labels}
        lower = text.lower()
        doc = self._nlp(text)

        # Sentence boundaries: single short sentence often indicates headings/captions
        sent_count = sum(1 for _ in doc.sents) if "parser" in self._nlp.pipe_names or len(doc) else 1
        token_count = len([t for t in doc if not t.is_space])

        if _RE_CAPTION.match(text):
            cues["caption"] = cues.get("caption", 0.0) + 0.35
        if _RE_REFERENCE.match(text) or "doi:" in lower or "et al." in lower:
            cues["reference"] = cues.get("reference", 0.0) + 0.30
        if "|" in text and "," in text:
            cues["table"] = cues.get("table", 0.0) + 0.25
        if "figure" in lower and any(ch.isdigit() for ch in text):
            cues["figure"] = cues.get("figure", 0.0) + 0.20

        if sent_count <= 1 and token_count <= 10 and not text.endswith("."):
            cues["heading_h2"] = cues.get("heading_h2", 0.0) + 0.12
            cues["heading_h3"] = cues.get("heading_h3", 0.0) + 0.10
        if text.isupper() and token_count <= 8:
            cues["heading_h1"] = cues.get("heading_h1", 0.0) + 0.18

        return cues

    def _heuristic_label(self, text: str, labels: List[str]) -> Tuple[str, float]:
        lower = text.lower().strip()
        wc = len(text.split())

        if "caption" in labels and _RE_CAPTION.match(text):
            return "caption", 0.72
        if "reference" in labels and (_RE_REFERENCE.match(text) or "doi:" in lower or "et al." in lower):
            return "reference", 0.71
        if "table" in labels and "|" in text and "," in text:
            return "table", 0.70
        if "figure" in labels and "figure" in lower:
            return "figure", 0.68

        if "heading_h1" in labels and _RE_H1.match(text):
            return "heading_h1", 0.74
        if "heading_h2" in labels and _RE_H2.match(text):
            return "heading_h2", 0.72
        if "heading_h3" in labels and _RE_H3.match(text):
            return "heading_h3", 0.70
        if any(l in labels for l in HEADING_LABELS) and text.isupper() and wc <= 8:
            return "heading_h1", 0.68

        return ("paragraph" if "paragraph" in labels else labels[0], 0.62)


ai_element_classifier = AIElementClassifier()
