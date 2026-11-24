"""
plagiarism/local_check.py — Stage 1 local corpus plagiarism signals.

Why Stage 1 exists (FYP):
  Exact/near-exact (MinHash + LSH) and semantic (embeddings + FAISS) checks run
  entirely on-device against a pre-indexed local corpus. This is deterministic,
  incurs zero per-token API cost, and is fast enough to score every sentence in
  the input document. Only highly suspicious sentences later justify optional
  web verification (Stage 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set

from plagiarism import config
from plagiarism.corpus_index import (
    CorpusIndex,
    embed_texts,
    jaccard_from_minhash,
    text_to_minhash,
    tokenize,
)


@dataclass
class ExactMatchResult:
    """Outcome of shingling + MinHash + LSH against the local corpus."""
    score: float  # Estimated Jaccard vs best corpus neighbour [0, 1]
    matched_source: Optional[str]
    matched_text: Optional[str]
    candidate_count: int = 0
    # Distinct corpus reports matched at/above the exact flag threshold.
    source_count: int = 0


@dataclass
class SemanticMatchResult:
    """Outcome of embedding + FAISS nearest-neighbour search."""
    score: float  # Cosine similarity vs best neighbour [0, 1]
    matched_source: Optional[str]
    matched_text: Optional[str]
    flagged: bool = False  # True when score >= SEMANTIC_SIMILARITY_THRESHOLD
    # Distinct corpus reports matched at/above the semantic threshold.
    source_count: int = 0


@dataclass
class LocalSentenceResult:
    """Combined Stage-1 verdict for a single input sentence/chunk."""
    sentence: str
    chunk_id: str
    exact: ExactMatchResult
    semantic: SemanticMatchResult
    local_suspicion_score: float
    match_type: str  # "exact" | "semantic" | "both" | "none"
    matched_corpus_source: Optional[str]
    # Crossed its own signal threshold (exact OR semantic).
    flagged: bool = False
    # Matches many different reports → common FYP phrasing, not counted.
    boilerplate: bool = False
    # Quotation / in-text citation → reported but not counted.
    quoted: bool = False
    cited: bool = False
    matched_text: Optional[str] = None

    @property
    def counts_toward_score(self) -> bool:
        """Only flagged sentences that are not boilerplate, quoted or cited count."""
        return self.flagged and not (self.boilerplate or self.quoted or self.cited)


# ── Sentence-level exemptions (pure, unit-testable) ──────────────────────────

_QUOTED_SPAN_RE = re.compile(r"[\"“”]([^\"“”]+)[\"“”]")

# [12] · [3, 4] · [5-7] · (Ali, 2021) · (Smith et al., 2019) · Ali and Raza (2020)
_CITATION_RE = re.compile(
    r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]"
    r"|\(\s*[A-Z][A-Za-z'\-]+(?:\s+et\s+al\.?|\s*(?:&|and)\s*[A-Z][A-Za-z'\-]+)?"
    r",?\s*(?:19|20)\d{2}[a-z]?\s*\)"
    r"|[A-Z][A-Za-z'\-]+(?:\s+et\s+al\.?|\s+(?:&|and)\s+[A-Z][A-Za-z'\-]+)?\s*\(\s*(?:19|20)\d{2}[a-z]?\s*\)"
)


def is_quoted(sentence: str, min_fraction: float = config.QUOTE_MIN_FRACTION) -> bool:
    """True when most of the sentence's words sit inside quotation marks."""
    total = len(tokenize(sentence))
    if total == 0:
        return False
    quoted = sum(len(tokenize(m.group(1))) for m in _QUOTED_SPAN_RE.finditer(sentence))
    return quoted / total >= min_fraction


def has_citation(sentence: str) -> bool:
    """True when the sentence carries an IEEE / APA style in-text citation."""
    return bool(_CITATION_RE.search(sentence or ""))


def is_flagged(
    exact: "ExactMatchResult",
    semantic: "SemanticMatchResult",
    exact_threshold: Optional[float] = None,
    semantic_threshold: Optional[float] = None,
) -> bool:
    """Each signal is judged against its own threshold (never a shared max())."""
    if exact_threshold is None:
        exact_threshold = config.FLAG_SCORE_THRESHOLD
    if semantic_threshold is None:
        semantic_threshold = config.SEMANTIC_SIMILARITY_THRESHOLD
    return exact.score >= exact_threshold or semantic.score >= semantic_threshold


# ── Exact / near-exact ───────────────────────────────────────────────────────

def check_exact_match(sentence: str, corpus: CorpusIndex) -> ExactMatchResult:
    """
    Query MinHashLSH for near-duplicate corpus sentences, then rank by Jaccard.

    Returns the best Jaccard estimate and its corpus filename. Empty / short
    sentences score 0.
    """
    words = tokenize(sentence)
    if len(words) < config.MIN_SENTENCE_WORDS:
        return ExactMatchResult(score=0.0, matched_source=None, matched_text=None)

    query_mh = text_to_minhash(sentence)
    try:
        keys = corpus.lsh.query(query_mh)
    except Exception:
        keys = []

    best_score = 0.0
    best_source: Optional[str] = None
    best_text: Optional[str] = None
    hit_sources: Set[str] = set()

    for key in keys:
        entry = corpus.minhash_by_key.get(key)
        if entry is None:
            continue
        source, text, corpus_mh = entry
        score = jaccard_from_minhash(query_mh, corpus_mh)
        if score >= config.FLAG_SCORE_THRESHOLD:
            hit_sources.add(source)
        if score > best_score:
            best_score = score
            best_source = source
            best_text = text

    # If LSH returned nothing, still try a brute-force top sample is overkill;
    # score stays 0 — semantic stage covers paraphrases.
    return ExactMatchResult(
        score=float(best_score),
        matched_source=best_source,
        matched_text=best_text,
        candidate_count=len(keys),
        source_count=len(hit_sources),
    )


# ── Semantic ─────────────────────────────────────────────────────────────────

def check_semantic_similarity(
    sentence: str,
    corpus: CorpusIndex,
    threshold: float = config.SEMANTIC_SIMILARITY_THRESHOLD,
    top_k: int = config.FAISS_TOP_K,
) -> SemanticMatchResult:
    """
    Embed `sentence` and query the FAISS IndexFlatIP corpus index.

    Cosine similarity == inner product because corpus (and query) vectors are
    L2-normalised at index time / encode time.
    """
    words = tokenize(sentence)
    if len(words) < config.MIN_SENTENCE_WORDS:
        return SemanticMatchResult(
            score=0.0, matched_source=None, matched_text=None, flagged=False
        )
    if corpus.faiss_index.ntotal == 0:
        return SemanticMatchResult(
            score=0.0, matched_source=None, matched_text=None, flagged=False
        )

    return check_semantic_similarity_batch(
        [sentence], corpus, threshold=threshold, top_k=top_k
    )[0]


def check_semantic_similarity_batch(
    sentences: Sequence[str],
    corpus: CorpusIndex,
    threshold: float = config.SEMANTIC_SIMILARITY_THRESHOLD,
    top_k: int = config.FAISS_TOP_K,
) -> List[SemanticMatchResult]:
    """
    Batch embedding variant — more efficient for full-document Stage 1 passes.
    """
    results: List[SemanticMatchResult] = []
    if not sentences:
        return results
    if corpus.faiss_index.ntotal == 0:
        return [
            SemanticMatchResult(score=0.0, matched_source=None, matched_text=None)
            for _ in sentences
        ]

    # Pad empty/short sentences with a dummy then overwrite — keeps one encode call.
    usable_flags = [len(tokenize(s)) >= config.MIN_SENTENCE_WORDS for s in sentences]
    encode_inputs = [
        s if ok else "placeholder" for s, ok in zip(sentences, usable_flags)
    ]
    query_vecs = embed_texts(encode_inputs, normalize=True)
    k = min(top_k, corpus.faiss_index.ntotal)
    scores_mat, indices_mat = corpus.faiss_index.search(query_vecs, k)

    for i, ok in enumerate(usable_flags):
        if not ok:
            results.append(
                SemanticMatchResult(
                    score=0.0, matched_source=None, matched_text=None, flagged=False
                )
            )
            continue

        best_score = 0.0
        best_source: Optional[str] = None
        best_text: Optional[str] = None
        hit_sources: Set[str] = set()
        for score, idx in zip(scores_mat[i], indices_mat[i]):
            if idx < 0:
                continue
            # Clamp floating-point noise outside [0, 1] for cosine of unit vectors.
            sim = max(0.0, min(1.0, float(score)))
            if sim >= threshold:
                hit_sources.add(corpus.sentence_sources[idx])
            if sim > best_score:
                best_score = sim
                best_source = corpus.sentence_sources[idx]
                best_text = corpus.sentence_texts[idx]

        results.append(
            SemanticMatchResult(
                score=best_score,
                matched_source=best_source,
                matched_text=best_text,
                flagged=best_score >= threshold,
                source_count=len(hit_sources),
            )
        )
    return results


# ── Combine signals ──────────────────────────────────────────────────────────

def combine_local_scores(
    exact: ExactMatchResult,
    semantic: SemanticMatchResult,
    semantic_threshold: float = config.SEMANTIC_SIMILARITY_THRESHOLD,
) -> tuple[float, str, Optional[str]]:
    """
    Merge exact + semantic into a single local_suspicion_score and match_type.

    Score is max(exact.jaccard, semantic.cosine). Match type uses 'exact' when
    Jaccard leads (or ties with a solid exact hit), 'semantic' when cosine
    exceeds the semantic flag threshold and dominates, and 'both' when both
    signals are meaningfully elevated.
    """
    score = max(exact.score, semantic.score)

    exact_hit = exact.score >= config.FLAG_SCORE_THRESHOLD
    semantic_hit = semantic.score >= semantic_threshold

    if exact_hit and semantic_hit:
        match_type = "both"
    elif exact_hit or (exact.score >= semantic.score and exact.score > 0):
        match_type = "exact" if exact.score > 0 else "none"
    elif semantic_hit or semantic.score > 0:
        match_type = "semantic" if semantic.score > 0 else "none"
    else:
        match_type = "none"

    # Prefer the source from the stronger signal.
    if exact.score >= semantic.score:
        source = exact.matched_source or semantic.matched_source
    else:
        source = semantic.matched_source or exact.matched_source

    # Refine match_type labels for the report schema (exact | semantic | both).
    if match_type == "none" and score > 0:
        match_type = "exact" if exact.score >= semantic.score else "semantic"

    return float(score), match_type, source


def analyze_sentence_local(
    sentence: str,
    chunk_id: str,
    corpus: CorpusIndex,
    semantic: Optional[SemanticMatchResult] = None,
) -> LocalSentenceResult:
    """
    Run both local checks for one sentence and return a combined result.

    Pass a precomputed `semantic` result when using batch embedding.
    """
    exact = check_exact_match(sentence, corpus)
    if semantic is None:
        semantic = check_semantic_similarity(sentence, corpus)

    suspicion, match_type, source = combine_local_scores(exact, semantic)
    flagged = is_flagged(exact, semantic)
    if exact.score >= semantic.score:
        matched_text = exact.matched_text or semantic.matched_text
    else:
        matched_text = semantic.matched_text or exact.matched_text
    # Same sentence found in many different reports → template / common phrasing.
    boilerplate = (
        max(exact.source_count, semantic.source_count) >= config.BOILERPLATE_MIN_SOURCES
    )
    return LocalSentenceResult(
        sentence=sentence,
        chunk_id=chunk_id,
        exact=exact,
        semantic=semantic,
        local_suspicion_score=suspicion,
        match_type=match_type,
        matched_corpus_source=source,
        flagged=flagged,
        boilerplate=flagged and boilerplate,
        quoted=flagged and is_quoted(sentence),
        cited=flagged and has_citation(sentence),
        matched_text=matched_text,
    )


def analyze_document_local(
    sentences: Sequence[dict],
    corpus: CorpusIndex,
) -> List[LocalSentenceResult]:
    """
    Stage 1 over a full document.

    Args:
        sentences: Iterable of ``{"text": str, "chunk_id": str}`` dicts
                   (already-parsed chunks from the Formatify pipeline).
        corpus: Loaded CorpusIndex.

    Returns:
        Per-sentence LocalSentenceResult list (includes low-score sentences;
        filtering for the report happens in the orchestrator).
    """
    texts = [str(s.get("text", "")) for s in sentences]
    semantic_batch = check_semantic_similarity_batch(texts, corpus)

    results: List[LocalSentenceResult] = []
    for item, sem in zip(sentences, semantic_batch):
        text = str(item.get("text", ""))
        chunk_id = str(item.get("chunk_id", ""))
        results.append(analyze_sentence_local(text, chunk_id, corpus, semantic=sem))
    return results
