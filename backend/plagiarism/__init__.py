"""
plagiarism — Hybrid local-corpus + selective web plagiarism detection for Formatify.

Stage 1 (always): MinHash/LSH exact-ish matching + MiniLM/FAISS semantic matching
against the local FYP corpus (``fyp_corpus/``). Deterministic, offline, cost-efficient.

Stage 2 (selective): Google Custom Search only for top-K suspicious sentences.
No LLM API calls in this package.

Setup:
  1. Copy previous FYP reports into ``plagiarism/fyp_reports_raw/``
  2. Run ``python -m plagiarism.ingest_corpus --rebuild-index`` from backend/
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "detect_plagiarism",
    "detect_plagiarism_sync",
    "build_corpus_index",
    "load_corpus_index",
    "check_document_against_fyp_corpus",
]


def __getattr__(name: str) -> Any:
    # Lazy exports keep `import plagiarism` light (embedding model not loaded yet).
    if name in ("detect_plagiarism", "detect_plagiarism_sync"):
        from plagiarism.detector import detect_plagiarism, detect_plagiarism_sync

        return {
            "detect_plagiarism": detect_plagiarism,
            "detect_plagiarism_sync": detect_plagiarism_sync,
        }[name]
    if name in ("build_corpus_index", "load_corpus_index"):
        from plagiarism.corpus_index import build_corpus_index, load_corpus_index

        return {
            "build_corpus_index": build_corpus_index,
            "load_corpus_index": load_corpus_index,
        }[name]
    if name == "check_document_against_fyp_corpus":
        from plagiarism.pipeline import check_document_against_fyp_corpus

        return check_document_against_fyp_corpus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
