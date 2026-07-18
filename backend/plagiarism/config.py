"""
plagiarism/config.py — Central configuration for the hybrid plagiarism detector.

All tunables live here so Stage 1 (local corpus) and Stage 2 (selective web
verification) stay easy to adjust for FYP experiments without hunting through
implementation code.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
# Package-local defaults; override via env if needed.
_PACKAGE_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _PACKAGE_DIR.parent


def _resolve_backend_path(raw: str, default_relative: str) -> Path:
    """Resolve absolute paths as-is; relative paths against backend/."""
    value = (raw or default_relative).strip()
    path = Path(value)
    if path.is_absolute():
        return path
    return (_BACKEND_DIR / path).resolve()


# Folder of reference FYP documents (TXT preferred; DOCX/PDF also accepted).
# Default: backend/plagiarism/fyp_corpus
CORPUS_DIR = _resolve_backend_path(
    os.getenv("PLAGIARISM_CORPUS_DIR", ""),
    "plagiarism/fyp_corpus",
)

# Where MinHashLSH + FAISS artefacts are cached on disk.
INDEX_CACHE_DIR = _resolve_backend_path(
    os.getenv("PLAGIARISM_INDEX_DIR", ""),
    "plagiarism/cache",
)

MINHASH_INDEX_FILE = INDEX_CACHE_DIR / "minhash_lsh.pkl"
FAISS_INDEX_FILE = INDEX_CACHE_DIR / "faiss.index"
FAISS_META_FILE = INDEX_CACHE_DIR / "faiss_meta.pkl"
CORPUS_META_FILE = INDEX_CACHE_DIR / "corpus_meta.pkl"

# ── Stage 1 — Exact / near-exact (shingling + MinHash + LSH) ─────────────────
# 5-word shingles balance specificity vs. recall for sentence-length chunks.
SHINGLE_SIZE = 5

# Number of MinHash permutations (higher → better Jaccard estimates, slower).
MINHASH_NUM_PERM = 128

# LSH band threshold: candidates with Jaccard >= this may be returned by LSH.
# Kept moderate so near-duplicates surface; final ranking still uses Jaccard.
LSH_THRESHOLD = 0.5

# ── Stage 1 — Semantic (sentence-transformers + FAISS) ───────────────────────
# Local embedding model — no API calls.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Cosine similarity above this flags a sentence as semantically suspicious.
SEMANTIC_SIMILARITY_THRESHOLD = float(
    os.getenv("PLAGIARISM_SEMANTIC_THRESHOLD", "0.85")
)

# How many FAISS nearest neighbours to retrieve per query sentence.
FAISS_TOP_K = 3

# ── Combining local signals ──────────────────────────────────────────────────
# local_suspicion_score = max(exact_jaccard, semantic_cosine).
# Sentences below this are omitted from flagged_sentences in the report.
FLAG_SCORE_THRESHOLD = float(os.getenv("PLAGIARISM_FLAG_THRESHOLD", "0.5"))

# ── Stage 2 — Selective web verification ─────────────────────────────────────
# Only sentences with local_suspicion_score above this enter Stage 2.
# If nothing crosses this bar, Stage 2 is skipped entirely (cost control).
WEB_VERIFY_SCORE_THRESHOLD = float(
    os.getenv("PLAGIARISM_WEB_THRESHOLD", "0.6")
)

# Top-K most suspicious sentences to send to Google Custom Search.
WEB_VERIFY_TOP_K = int(os.getenv("PLAGIARISM_WEB_TOP_K", "8"))

# Hard cap on Google API calls per document (rate limit).
WEB_VERIFY_MAX_CALLS = 10

# Truncate query sentences longer than this before calling Google.
WEB_QUERY_MAX_WORDS = 30

# Number of Google search results to inspect per query.
WEB_SEARCH_NUM_RESULTS = 3

# Minimum overlap (Jaccard on word sets, or substring hit) to mark web_verified.
WEB_OVERLAP_THRESHOLD = 0.45

# Google Custom Search credentials — never hardcode keys here.
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# ── Sentence filtering ───────────────────────────────────────────────────────
# Ignore very short fragments (noise / headings) during detection.
MIN_SENTENCE_WORDS = 8
