"""
Layer 2 — Heading Normalizer & Synonym Matcher
================================================
Takes the heading blocks from Layer 1 and matches each one against
a required-sections list using 4 progressive layers:

    Layer 1 → Exact match          (fastest, zero false negatives)
    Layer 2 → Manual synonym dict  (catches "Intro", "Lit Review", etc.)
    Layer 3 → Fuzzy match          (catches typos: "Methdology")
    Layer 4 → Semantic similarity  (MiniLM, 80 MB, CPU-fast)

Why this order?
  • Exact  →  never wrong
  • Synonyms → domain knowledge, catches what cosine misses ("Intro" ≈ 0.71)
  • Fuzzy  →  typos & abbreviations
  • Semantic → everything else

Usage
------
from services.heading_normalizer import HeadingNormalizer

hn = HeadingNormalizer()
result = hn.match_headings(
    extracted_headings=["Intro", "Lit Review", "Methdology", "Conclusion"],
    required_sections=["Introduction", "Literature Review", "Methodology",
                       "Results", "Conclusion", "References"]
)
print(result)
"""

from __future__ import annotations

import re
import os
import json
import unicodedata
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Optional heavy deps — loaded lazily so the module still imports if missing
# ──────────────────────────────────────────────────────────────────────────────
_fuzz   = None   # rapidfuzz
_model  = None   # sentence-transformers SentenceTransformer
_np     = None   # numpy


def _load_fuzz():
    global _fuzz
    if _fuzz is None:
        try:
            from rapidfuzz import fuzz as _f
            _fuzz = _f
        except ImportError:
            raise ImportError(
                "rapidfuzz is required for Layer 3 fuzzy matching.\n"
                "Run: pip install rapidfuzz"
            )
    return _fuzz


def _load_model():
    global _model, _np
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            _model = SentenceTransformer("all-MiniLM-L6-v2")   # 80 MB, CPU fine
            _np    = np
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for Layer 4 semantic matching.\n"
                "Run: pip install sentence-transformers"
            )
    return _model, _np


# ──────────────────────────────────────────────────────────────────────────────
# Manual synonym dictionary
# Add / remove entries here as you learn your university's conventions
# ──────────────────────────────────────────────────────────────────────────────
SYNONYM_MAP: Dict[str, List[str]] = {
    # Introduction
    "introduction": [
        "intro", "background", "overview", "preface",
        "background and introduction", "project introduction",
    ],
    # Problem Statement
    "problem statement": [
        "problem", "problem definition", "problem description",
        "the problem", "statement of problem", "problem formulation",
    ],
    # Objectives
    "objectives": [
        "objective", "project objectives", "aims", "goals",
        "aims and objectives", "project aims",
    ],
    # Scope
    "scope": [
        "project scope", "scope of project", "scope of work",
        "scope and limitations", "limitations and scope",
    ],
    # Literature Review
    "literature review": [
        "lit review", "related work", "related works",
        "background research", "prior work", "existing work",
        "survey of literature", "review of literature",
    ],
    # Methodology
    "methodology": [
        "method", "methods", "approach", "research methodology",
        "proposed methodology", "research design", "research approach",
        "technical approach", "system design and methodology",
    ],
    # System Design
    "system design": [
        "design", "architecture", "system architecture",
        "high level design", "detailed design", "software design",
        "technical design",
    ],
    # Implementation
    "implementation": [
        "development", "coding", "system implementation",
        "technical implementation", "execution",
    ],
    # Results
    "results": [
        "findings", "outcomes", "experimental results",
        "results and discussion", "results and analysis",
        "output", "outputs",
    ],
    # Evaluation
    "evaluation": [
        "testing", "test", "analysis", "performance evaluation",
        "performance analysis", "system evaluation", "testing and evaluation",
        "validation",
    ],
    # Conclusion
    "conclusion": [
        "conclusions", "summary", "final remarks", "closing remarks",
        "concluding remarks", "conclusion and future work",
    ],
    # Future Work
    "future work": [
        "future works", "recommendations", "future recommendations",
        "future scope", "future enhancements",
    ],
    # Abstract
    "abstract": [
        "executive summary", "synopsis", "project abstract",
    ],
    # References
    "references": [
        "reference", "bibliography", "citations", "works cited",
        "list of references",
    ],
    # Acknowledgements
    "acknowledgements": [
        "acknowledgement", "acknowledgment", "acknowledgments",
    ],
    # Feasibility Study
    "feasibility study": [
        "feasibility", "feasibility analysis", "project feasibility",
        "technical feasibility",
    ],
    # Risk Analysis
    "risk analysis": [
        "risks", "risk assessment", "risk management",
        "risk identification",
    ],
}

# Build a reverse lookup: alias → canonical
_REVERSE_SYNONYM: Dict[str, str] = {}
for _canonical, _aliases in SYNONYM_MAP.items():
    for _alias in _aliases:
        _REVERSE_SYNONYM[_alias.lower()] = _canonical


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MatchResult:
    """Result for a single required section."""
    required:        str
    matched_heading: Optional[str]   # text from the document, or None
    match_layer:     Optional[str]   # "exact" | "synonym" | "fuzzy" | "semantic" | None
    confidence:      float           # 0.0 – 1.0
    status:          str             # "found" | "missing"


@dataclass
class NormalizerReport:
    """Full report returned by HeadingNormalizer.match_headings()."""
    matches:          List[MatchResult]
    found:            List[str]       # required sections that were found
    missing:          List[str]       # required sections not found
    extra_headings:   List[str]       # doc headings not matched to any required section
    total_required:   int
    total_found:      int


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────

class HeadingNormalizer:
    """
    4-layer heading matcher.

    Parameters
    ----------
    fuzzy_threshold : float
        rapidfuzz score (0-100) to consider a fuzzy match.  Default 80.
    semantic_threshold : float
        Cosine similarity (0-1) to consider a semantic match.  Default 0.75.
        (Lower than the 0.85 in the comparison doc — avoids missing "Intro".)
    use_semantic : bool
        Set False to skip Layer 4 (useful on very low-end machines).
    """

    def __init__(
        self,
        fuzzy_threshold: float    = 80.0,
        semantic_threshold: float = 0.35,
        use_semantic: bool        = True,
    ):
        self.fuzzy_threshold    = fuzzy_threshold
        self.semantic_threshold = semantic_threshold
        self.use_semantic       = use_semantic

    # ── Public API ────────────────────────────────────────────────────────────

    def match_headings(
        self,
        extracted_headings: List[str],
        required_sections:  List[str],
    ) -> NormalizerReport:
        """
        Match every required section against the headings found in the document.

        Parameters
        ----------
        extracted_headings : list of heading texts (from Layer 1 blocks)
        required_sections  : list of canonical section names from your template

        Returns
        -------
        NormalizerReport
        """
        norm_extracted = [self._normalize(h) for h in extracted_headings]
        norm_required  = [self._normalize(r) for r in required_sections]

        # Track which extracted headings have been claimed
        claimed: Dict[int, bool] = {i: False for i in range(len(norm_extracted))}

        matches: List[MatchResult] = []

        for req_raw, req_norm in zip(required_sections, norm_required):
            result, claimed_idx = self._match_one(
                req_raw, req_norm,
                extracted_headings, norm_extracted,
                claimed,
            )
            if claimed_idx is not None:
                claimed[claimed_idx] = True
            matches.append(result)

        # Unclaimed headings → "extra"
        extra = [extracted_headings[i] for i, used in claimed.items() if not used]

        found   = [m.required for m in matches if m.status == "found"]
        missing = [m.required for m in matches if m.status == "missing"]

        return NormalizerReport(
            matches        = matches,
            found          = found,
            missing        = missing,
            extra_headings = extra,
            total_required = len(required_sections),
            total_found    = len(found),
        )

    def normalize_heading(self, text: str) -> str:
        """Public wrapper around internal normalizer (useful for debugging)."""
        return self._normalize(text)

    # ── Internal matching ─────────────────────────────────────────────────────

    def _match_one(
        self,
        req_raw:  str,
        req_norm: str,
        extracted_raw:  List[str],
        extracted_norm: List[str],
        claimed: Dict[int, bool],
    ) -> Tuple[MatchResult, Optional[int]]:
        """Try all 4 layers in order for a single required section."""

        candidates = [(i, h) for i, h in enumerate(extracted_norm) if not claimed[i]]

        # ── Layer 1: Exact ────────────────────────────────────────────────────
        for i, h_norm in candidates:
            if req_norm == h_norm:
                return self._ok(req_raw, extracted_raw[i], "exact", 1.0), i

        # ── Layer 2: Synonym dict ─────────────────────────────────────────────
        # a) Is the required section an alias for something in the document?
        req_canonical = _REVERSE_SYNONYM.get(req_norm, req_norm)
        for i, h_norm in candidates:
            h_canonical = _REVERSE_SYNONYM.get(h_norm, h_norm)
            if req_canonical == h_canonical:
                return self._ok(req_raw, extracted_raw[i], "synonym", 0.95), i

        # b) Is the document heading a known synonym of the required section?
        if req_norm in SYNONYM_MAP:
            aliases = [a.lower() for a in SYNONYM_MAP[req_norm]]
            for i, h_norm in candidates:
                if h_norm in aliases:
                    return self._ok(req_raw, extracted_raw[i], "synonym", 0.95), i

        # ── Layer 2.5: Contains (Substring) ───────────────────────────────────
        # If the template heading (e.g. 'Motivation') is inside the 
        # document heading (e.g. 'Project Motivation and Significance')
        for i, h_norm in candidates:
            if req_norm in h_norm:
                return self._ok(req_raw, extracted_raw[i], "contains", 0.9), i

        # ── Layer 3: Fuzzy ────────────────────────────────────────────────────
        fuzz = _load_fuzz()
        best_score, best_idx = 0.0, -1
        for i, h_norm in candidates:
            score = fuzz.token_sort_ratio(req_norm, h_norm)
            if score > best_score:
                best_score, best_idx = score, i

        if best_score >= self.fuzzy_threshold and best_idx >= 0:
            return self._ok(
                req_raw,
                extracted_raw[best_idx],
                "fuzzy",
                round(best_score / 100, 2),
            ), best_idx

        # ── Layer 4: Semantic ─────────────────────────────────────────────────
        if self.use_semantic and candidates:
            try:
                model, np = _load_model()
                cand_texts = [extracted_raw[i] for i, _ in candidates]
                all_texts  = [req_raw] + cand_texts
                embeddings = model.encode(all_texts, normalize_embeddings=True)
                req_emb    = embeddings[0]
                cand_embs  = embeddings[1:]

                sims = (cand_embs @ req_emb)   # cosine since normalized
                best_pos = int(np.argmax(sims))
                best_sim = float(sims[best_pos])

                if best_sim >= self.semantic_threshold:
                    actual_idx = candidates[best_pos][0]
                    return self._ok(
                        req_raw,
                        extracted_raw[actual_idx],
                        "semantic",
                        round(best_sim, 2),
                    ), actual_idx
            except ImportError:
                pass   # semantic unavailable, fall through

        # ── No match ──────────────────────────────────────────────────────────
        return MatchResult(
            required        = req_raw,
            matched_heading = None,
            match_layer     = None,
            confidence      = 0.0,
            status          = "missing",
        ), None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Lowercase, strip numbering/punctuation, collapse spaces.
        "1. Introduction" → "introduction"
        "2.3 Literature Review:" → "literature review"
        """
        # Unicode → ASCII (handles curly quotes, em-dashes, etc.)
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
        # Remove leading numbering: "1.", "1.2", "1.2.3", "Chapter 1"
        text = re.sub(r"^(chapter\s+\d+[\s\-:]*|\d+(\.\d+)*\.?\s*)", "", text, flags=re.IGNORECASE)
        text = text.lower()
        # Remove trailing punctuation
        text = text.rstrip(":.-– ")
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _ok(required: str, matched: str, layer: str, confidence: float) -> MatchResult:
        return MatchResult(
            required        = required,
            matched_heading = matched,
            match_layer     = layer,
            confidence      = confidence,
            status          = "found",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Convenience function (used by router & higher layers)
# ──────────────────────────────────────────────────────────────────────────────

def match_document_headings(
    extracted_headings: List[str],
    required_sections:  List[str],
    fuzzy_threshold:    float = 80.0,
    semantic_threshold: float = 0.75,
    use_semantic:       bool  = True,
) -> dict:
    """
    Thin wrapper that returns a plain dict (JSON-serialisable).
    Call this from routers or other services.
    """
    hn     = HeadingNormalizer(fuzzy_threshold, semantic_threshold, use_semantic)
    report = hn.match_headings(extracted_headings, required_sections)

    return {
        "total_required": report.total_required,
        "total_found":    report.total_found,
        "found":          report.found,
        "missing":        report.missing,
        "extra_headings": report.extra_headings,
        "matches": [
            {
                "required":        m.required,
                "matched_heading": m.matched_heading,
                "match_layer":     m.match_layer,
                "confidence":      m.confidence,
                "status":          m.status,
            }
            for m in report.matches
        ],
    }


def detect_headings_from_template(document_id: int, user_id: int, db) -> List[Dict]:
    """
    Retrieves document template and uses HeadingNormalizer (Layer 2)
    to identify headings based on template's required_sections.
    """
    from docx import Document
    
    # 1. Fetch doc and template
    doc_row = db.execute(
        "SELECT file_path, template_id FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id)
    ).fetchone()
    if not doc_row or not doc_row["template_id"]:
        return []

    tmpl_row = db.execute(
        "SELECT required_sections FROM templates WHERE id = ?",
        (doc_row["template_id"],)
    ).fetchone()
    if not tmpl_row:
        return []

    # 2. Parse required sections
    try:
        raw_sections = json.loads(tmpl_row["required_sections"])
        required_names = []
        for s in raw_sections:
            if isinstance(s, dict):
                required_names.append(s["name"])
            else:
                required_names.append(str(s))
    except:
        return []

    # 3. Extract all paragraphs from docx
    file_path = doc_row["file_path"]
    working_copy = f"uploads/working/doc_{document_id}_working.docx"
    if os.path.exists(working_copy):
        file_path = working_copy

    if not os.path.exists(file_path):
        return []
    
    doc = Document(file_path)
    # Filter out empty paragraphs to match para_index correctly
    paras = []
    for i, p in enumerate(doc.paragraphs):
        paras.append({"text": p.text.strip(), "index": i})
    
    heading_texts = [p["text"] for p in paras if p["text"]]
    
    # 4. Use Normalizer (inherits 0.35 threshold and substring match)
    hn = HeadingNormalizer()
    report = hn.match_headings(heading_texts, required_names)
    
    matches = []
    # Build text -> original index map
    text_to_idx = {}
    for p in paras:
        if p["text"] and p["text"] not in text_to_idx:
            text_to_idx[p["text"]] = p["index"]
            
    for match in report.matches:
        if match.status == "found" and match.matched_heading:
            matches.append({
                "para_index":   text_to_idx.get(match.matched_heading, -1),
                "heading_level": 1,
                "heading":       match.required,      # consistent key
                "matched_text":  match.matched_heading
            })
            
    return matches