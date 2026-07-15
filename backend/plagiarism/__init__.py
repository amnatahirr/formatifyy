"""
plagiarism — Hybrid local-corpus + selective web plagiarism detection for Formatify.

Stage 1 (always): MinHash/LSH exact-ish matching + MiniLM/FAISS semantic matching
against a local .txt corpus. Deterministic, offline, cost-efficient.

Stage 2 (selective): Google Custom Search only for top-K suspicious sentences.
No LLM API calls in this package.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "detect_plagiarism",
    "detect_plagiarism_sync",
    "build_corpus_index",
    "load_corpus_index",
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
