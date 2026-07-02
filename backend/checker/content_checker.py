"""
checker/content_checker.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HYBRID content checker — Zero-Shot primary, Trained model secondary.

FALSE POSITIVE FIXES applied:
  1. Trained model only used for HIGH-CONFIDENCE cases (prob > 0.80)
     because the 60%-accuracy model causes too many false positives
  2. Zero-shot requires a LARGER gap (0.30 default, 0.45 for similar pairs)
     to flag a mismatch — reduces noise
  3. Sections with < 150 chars of content are skipped entirely
     (too short to judge meaningfully)
  4. Headings not in the canonical list are SKIPPED by zero-shot
     (subsections like "Python (Django or FastAPI):" should not be checked
      against the heading embedding space)
  5. Synonym check still runs for all headings (rule-based, always accurate)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import re
import logging
import pickle
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

EMBEDDER_NAME = "all-MiniLM-L6-v2"
MODEL_PATH    = os.path.join(os.path.dirname(__file__), "content_classifier.pkl")

# ── How much content is needed before we bother checking ──────────────────────
MIN_CONTENT_LEN = 150   # chars — short sections get too many false positives

# ── Zero-shot thresholds ──────────────────────────────────────────────────────
# Gap = (best_other_score - own_score)
# Only flag if gap exceeds this threshold.
MARGIN_DEFAULT = 0.30   # for clearly different sections
MARGIN_SIMILAR = 0.45   # for naturally similar sections (Abstract/Intro etc.)
MIN_OWN_SCORE  = 0.35   # if content already scores this well on its heading → skip

# ── Trained model threshold ───────────────────────────────────────────────────
# Only use trained model prediction if it is THIS confident the content is wrong.
# At 60% overall accuracy we need high per-sample confidence to trust it.
TRAINED_MIN_PROB = 0.80  # require 80%+ probability of being wrong

# ── Canonical headings ─────────────────────────────────────────────────────────
# Zero-shot ONLY checks sections whose heading resolves to one of these.
# Any heading NOT in this list (subsections, custom headings) is skipped
# by zero-shot to avoid false positives on unknown content.
COMSATS_HEADINGS = [
    "Abstract", "Introduction", "Problem Statement", "Objectives", "Scope",
    "Background", "Motivation", "Literature Review", "Related Work",
    "Proposed Solution", "Methodology", "System Design", "Architecture",
    "Implementation", "Tools and Technologies", "Functional Requirements",
    "Non-Functional Requirements", "Testing", "Results", "Discussion",
    "Conclusion", "Future Work", "References", "Acknowledgements",
    "Feasibility Study", "Expected Outcomes",
]
CANONICAL_SET = {h.lower() for h in COMSATS_HEADINGS}

# ── Synonym map ────────────────────────────────────────────────────────────────
SYNONYM_MAP = {
    "abstract": "Abstract", "abstract:": "Abstract",
    "summary": "Abstract", "executive summary": "Abstract",
    "project summary": "Abstract",

    "introduction": "Introduction", "intro": "Introduction",
    "overview": "Introduction", "1 introduction": "Introduction",
    "1.1 introduction": "Introduction", "1. introduction": "Introduction",

    "problem statement": "Problem Statement",
    "problem definition": "Problem Statement",
    "problem": "Problem Statement",
    "1.2 problem statement": "Problem Statement",
    "1.3 problem statement": "Problem Statement",
    "issue statement": "Problem Statement",

    "objectives": "Objectives", "objective": "Objectives",
    "goals": "Objectives", "aims": "Objectives", "aim": "Objectives",
    "aims and objectives": "Objectives",

    "scope": "Scope", "project scope": "Scope",
    "scope of project": "Scope", "scope and limitations": "Scope",

    "background": "Background", "project background": "Background",
    "motivation": "Motivation", "rationale": "Motivation",
    "significance": "Motivation",

    "literature review": "Literature Review",
    "lit review": "Literature Review",
    "review of literature": "Literature Review",
    "existing system": "Literature Review",
    "2.1 literature review": "Literature Review",

    "related work": "Related Work", "prior work": "Related Work",

    "proposed solution": "Proposed Solution",
    "proposed system": "Proposed Solution",
    "proposed approach": "Proposed Solution",

    "methodology": "Methodology", "method": "Methodology",
    "methods": "Methodology", "approach": "Methodology",
    "research methodology": "Methodology",

    "system design": "System Design", "design": "System Design",
    "architecture": "Architecture", "system architecture": "Architecture",
    "software architecture": "Architecture",

    "implementation": "Implementation", "development": "Implementation",

    "tools and technologies": "Tools and Technologies",
    "tools & technologies": "Tools and Technologies",
    "tech stack": "Tools and Technologies",
    "technology stack": "Tools and Technologies",
    "tools used": "Tools and Technologies",

    "functional requirements": "Functional Requirements",
    "functional requirement": "Functional Requirements",
    "requirements": "Functional Requirements",

    "non-functional requirements": "Non-Functional Requirements",
    "non functional requirements": "Non-Functional Requirements",

    "testing": "Testing", "test cases": "Testing", "evaluation": "Testing",

    "results": "Results", "findings": "Results", "outcomes": "Results",

    "discussion": "Discussion", "analysis": "Discussion",

    "conclusion": "Conclusion", "concluding remarks": "Conclusion",
    "summary and conclusion": "Conclusion",

    "future work": "Future Work", "future scope": "Future Work",
    "future directions": "Future Work",
    "5.2 future work": "Future Work", "5.3 future work": "Future Work",

    "references": "References", "bibliography": "References",
    "citations": "References",

    "acknowledgement": "Acknowledgements",
    "acknowledgment": "Acknowledgements",
    "acknowledgments": "Acknowledgements",

    "feasibility study": "Feasibility Study",
    "feasibility": "Feasibility Study",

    "expected outcomes": "Expected Outcomes",
}

# ── Section pairs that are naturally similar ───────────────────────────────────
SIMILAR_PAIRS = {
    frozenset(["Abstract",                "Introduction"]),
    frozenset(["Introduction",            "Background"]),
    frozenset(["Problem Statement",       "Motivation"]),
    frozenset(["Objectives",              "Expected Outcomes"]),
    frozenset(["Methodology",             "Implementation"]),
    frozenset(["Results",                 "Discussion"]),
    frozenset(["Conclusion",              "Future Work"]),
    frozenset(["Literature Review",       "Related Work"]),
    frozenset(["System Design",           "Architecture"]),
    frozenset(["Functional Requirements", "Non-Functional Requirements"]),
}


def _normalize(heading: str) -> str:
    h = heading.strip().lower()
    h = re.sub(r"^\d+[\.\d]*\s*", "", h)
    h = re.sub(r"[:\-]+$", "", h)
    return h.strip()


def _resolve(heading: str) -> Optional[str]:
    """Map heading to canonical name, or None if it's a subsection/unknown."""
    lower = heading.strip().lower()
    if lower in SYNONYM_MAP:
        return SYNONYM_MAP[lower]
    norm = _normalize(heading)
    if norm in SYNONYM_MAP:
        return SYNONYM_MAP[norm]
    for h in COMSATS_HEADINGS:
        if h.lower() == norm:
            return h
    return None   # subsection or unknown — don't check


# ══════════════════════════════════════════════════════════════════════════════
class ContentChecker:

    def __init__(self):
        self._embedder           = None
        self._heading_embeddings = None
        self._clf                = None
        self._trained_available  = False
        self._load_embedder()
        self._load_trained_model()

    @property
    def _model_available(self):
        """Backwards compatibility for documents.py."""
        return self._trained_available or (self._embedder is not None)

    def _load_embedder(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(EMBEDDER_NAME)
            self._heading_embeddings = self._embedder.encode(
                COMSATS_HEADINGS, convert_to_numpy=True, show_progress_bar=False,
            )
            logger.info("[ContentChecker] Embedder ready.")
        except ImportError:
            logger.warning("[ContentChecker] pip install sentence-transformers")

    def _load_trained_model(self):
        if not os.path.exists(MODEL_PATH):
            logger.info("[ContentChecker] No trained model — zero-shot only.")
            return
        try:
            with open(MODEL_PATH, "rb") as f:
                self._clf = pickle.load(f)
            self._trained_available = True
            logger.info("[ContentChecker] Trained model loaded (used only at high confidence).")
        except Exception as e:
            logger.warning("[ContentChecker] Could not load trained model: %s", e)

    # ── Main public method ────────────────────────────────────────────────────

    def check(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        issues = []
        for section in sections:
            heading = (section.get("heading") or "").strip()
            content = (section.get("content") or "").strip()
            if not heading or not content:
                continue

            # 1. Synonym check — always runs, always accurate
            syn = self._check_synonym(heading)
            if syn:
                issues.append(syn)

            # 2. Content mismatch — only for canonical headings with enough content
            if len(content) >= MIN_CONTENT_LEN and self._embedder:
                canonical = _resolve(heading)
                if canonical is not None:   # skip subsections entirely
                    mismatch = self._check_content_hybrid(heading, canonical, content)
                    if mismatch:
                        issues.append(mismatch)

        return issues

    # ── Synonym detection ─────────────────────────────────────────────────────

    def _check_synonym(self, heading: str) -> Optional[Dict]:
        if heading in COMSATS_HEADINGS:
            return None
        canonical = _resolve(heading)
        if canonical and canonical != heading:
            return {
                "type":       "synonym_heading",
                "severity":   "warning",
                "code":       "SYNONYM_HEADING",
                "heading":    heading,
                "canonical":  canonical,
                "confidence": 1.0,
                "detection":  "rule_based",
                "mode":       "keyword",
                "message": (
                    f"'{heading}' is a variation of '{canonical}'. "
                    f"Rename it to '{canonical}' to match the template."
                ),
            }
        return None

    # ── Hybrid content mismatch ───────────────────────────────────────────────

    def _check_content_hybrid(self, heading: str, canonical: str,
                               content: str) -> Optional[Dict]:
        zs = self._zero_shot_signal(canonical, content)
        tr = self._trained_signal(canonical, content) if self._trained_available else None
        return self._combine(heading, canonical, zs, tr)

    def _zero_shot_signal(self, canonical: str, content: str) -> Optional[Dict]:
        own_idx = next((i for i, h in enumerate(COMSATS_HEADINGS)
                        if h.lower() == canonical.lower()), None)
        if own_idx is None:
            return None

        content_vec = self._embedder.encode([content[:512]], convert_to_numpy=True)[0]
        norms = np.linalg.norm(self._heading_embeddings, axis=1)
        sims  = (self._heading_embeddings @ content_vec) / (
            norms * np.linalg.norm(content_vec) + 1e-9)

        own_score  = float(sims[own_idx])
        best_idx   = int(np.argmax(sims))
        best_score = float(sims[best_idx])
        best_name  = COMSATS_HEADINGS[best_idx]

        if best_idx == own_idx:
            return {"flagged": False}
        if own_score >= MIN_OWN_SCORE:
            return {"flagged": False}

        pair   = frozenset([canonical, best_name])
        margin = MARGIN_SIMILAR if pair in SIMILAR_PAIRS else MARGIN_DEFAULT
        gap    = best_score - own_score

        if gap < margin:
            return {"flagged": False}

        return {
            "flagged":    True,
            "own_score":  round(own_score, 3),
            "best_name":  best_name,
            "best_score": round(best_score, 3),
            "gap":        round(gap, 3),
            "confidence": round(min(gap / 0.5, 1.0), 2),
        }

    def _trained_signal(self, canonical: str, content: str) -> Optional[Dict]:
        """
        Only trust the trained model when it is VERY confident (>= TRAINED_MIN_PROB).
        At 60% overall accuracy, low-confidence predictions are noise.
        """
        try:
            text = f"{canonical} [SEP] {content[:512]}"
            vec  = self._embedder.encode([text], convert_to_numpy=True)
            prob = self._clf.predict_proba(vec)[0]  # [p_wrong, p_correct]
            p_wrong = float(prob[0])

            if p_wrong >= TRAINED_MIN_PROB:
                return {"flagged": True, "confidence": round(p_wrong, 2)}
            else:
                return {"flagged": False}
        except Exception as e:
            logger.warning("[ContentChecker] Trained model error: %s", e)
            return None

    def _combine(self, heading, canonical, zs, tr) -> Optional[Dict]:
        zs_flagged = zs is not None and zs.get("flagged", False)
        tr_flagged = tr is not None and tr.get("flagged", False)

        if not zs_flagged and not tr_flagged:
            return None

        best_name  = zs.get("best_name",  "another section") if zs_flagged else "another section"
        own_score  = zs.get("own_score",  None) if zs_flagged else None
        best_score = zs.get("best_score", None) if zs_flagged else None

        if zs_flagged and tr_flagged:
            detection  = "hybrid"
            confidence = round(min(0.5 + (zs.get("gap", 0) +
                                          tr.get("confidence", 0)) / 2, 0.99), 2)
            severity   = "error"
            how = "Both the zero-shot similarity check and the trained model agree"
        elif zs_flagged:
            detection  = "zero_shot"
            confidence = zs.get("confidence", 0.5)
            severity   = "warning"
            how = "Semantic similarity check suggests"
        else:
            detection  = "trained"
            confidence = tr.get("confidence", 0.5)
            severity   = "warning"
            how = "The trained model suggests"

        message = f"{how} the content under '{heading}' may not belong here."
        if zs_flagged and best_name != "another section":
            message += (
                f" It scores {own_score} under '{canonical}'"
                f" but {best_score} under '{best_name}'."
                f" Consider moving this content to '{best_name}'."
            )

        return {
            "type":               "content_mismatch",
            "severity":           severity,
            "code":               "CONTENT_MISMATCH",
            "heading":            heading,
            "canonical_heading":  canonical,
            "best_match_heading": best_name,
            "own_similarity":     own_score,
            "best_match_score":   best_score,
            "confidence":         confidence,
            "detection":          detection,
            "mode":               detection,
            "message":            message,
        }

    @staticmethod
    def sections_from_blocks(blocks: List[Dict]) -> List[Dict]:
        sections = []
        cur_heading = ""
        cur_parts   = []
        for block in blocks:
            btype = block.get("type", "paragraph")
            text  = (block.get("text") or "").strip()
            if btype == "heading":
                if cur_heading:
                    sections.append({
                        "heading": cur_heading,
                        "content": " ".join(cur_parts).strip(),
                    })
                cur_heading = text
                cur_parts   = []
            elif text:
                cur_parts.append(text)
        if cur_heading:
            sections.append({
                "heading": cur_heading,
                "content": " ".join(cur_parts).strip(),
            })
        return sections
