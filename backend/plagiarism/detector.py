"""
plagiarism/detector.py — Orchestrates Stage 1 (local) + Stage 2 (selective web).

Pipeline position (Formatify):
  Runs after document ingestion and batching. Input is already-parsed text
  chunked into paragraphs/sentences — this module does not open DOCX/PDF files.

Design (FYP):
  * Stage 1 always runs: deterministic MinHash/LSH + sentence-transformers/FAISS
    against a local corpus. Fast, free, offline after model download.
  * Stage 2 is selective: Google Custom Search only for the top-K sentences whose
    local_suspicion_score exceeds WEB_VERIFY_SCORE_THRESHOLD, capped at
    WEB_VERIFY_MAX_CALLS. Skipped entirely when nothing is suspicious enough.
  * No Claude / GPT / Gemini calls anywhere in this module.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from dotenv import load_dotenv

# Allow `python plagiarism/detector.py` from backend/ without installing the package.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

load_dotenv(_BACKEND_ROOT / ".env")

from plagiarism import config
from plagiarism.corpus_index import (
    CorpusIndex,
    build_corpus_index,
    split_into_sentences,
    tokenize,
)
from plagiarism.local_check import LocalSentenceResult, analyze_document_local
from plagiarism.web_verify import WebVerifyResult, verify_sentence_on_web


# ── Input normalisation (pure) ───────────────────────────────────────────────

def normalize_chunks(
    document: Union[str, Sequence[Union[str, Dict[str, Any]]]],
) -> List[Dict[str, str]]:
    """
    Accept flexible pipeline inputs and return ``[{text, chunk_id}, ...]``.

    Supported forms:
      - raw document string (split into sentences)
      - list of strings
      - list of dicts with ``text`` / ``sentence`` and optional ``chunk_id`` /
        ``paragraph_id`` / ``id``
    """
    if isinstance(document, str):
        sentences = split_into_sentences(document)
        return [
            {"text": s, "chunk_id": f"sent_{i}"}
            for i, s in enumerate(sentences)
        ]

    chunks: List[Dict[str, str]] = []
    for i, item in enumerate(document):
        if isinstance(item, str):
            text = item.strip()
            chunk_id = f"chunk_{i}"
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("sentence") or "").strip()
            chunk_id = str(
                item.get("chunk_id")
                or item.get("paragraph_id")
                or item.get("id")
                or f"chunk_{i}"
            )
        else:
            continue
        if text:
            chunks.append({"text": text, "chunk_id": chunk_id})
    return chunks


def filter_checkable_sentences(
    chunks: Sequence[Dict[str, str]],
    min_words: int = config.MIN_SENTENCE_WORDS,
) -> List[Dict[str, str]]:
    """Drop empty / too-short fragments that cannot yield reliable matches."""
    out: List[Dict[str, str]] = []
    for c in chunks:
        if len(tokenize(c["text"])) >= min_words:
            out.append(c)
    return out


def _word_count(text: str) -> int:
    return len(tokenize(text))


def overall_plagiarism_score(local_results: Sequence[LocalSentenceResult]) -> float:
    """
    Document-level similarity index in [0, 1] — *coverage*, Turnitin-style:

        words in sentences that count as matched  /  words in all checked sentences

    A single 95% match in a 300-sentence report is ~0.3%, not 95%. Boilerplate,
    quoted and cited sentences are excluded from the numerator.
    """
    total = sum(_word_count(r.sentence) for r in local_results)
    if total == 0:
        return 0.0
    matched = sum(
        _word_count(r.sentence) for r in local_results if r.counts_toward_score
    )
    return round(matched / total, 4)


def mean_match_similarity(local_results: Sequence[LocalSentenceResult]) -> float:
    """Average similarity of the counted matches (how close the copies are)."""
    scores = [r.local_suspicion_score for r in local_results if r.counts_toward_score]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def source_breakdown(local_results: Sequence[LocalSentenceResult]) -> List[Dict[str, Any]]:
    """
    Per-source share of the document: ``[{source, coverage, matched_words,
    sentences}]`` sorted by coverage (highest first). Coverage is in [0, 1].
    """
    total = sum(_word_count(r.sentence) for r in local_results)
    if total == 0:
        return []
    by_source: Dict[str, Dict[str, Any]] = {}
    for r in local_results:
        if not r.counts_toward_score:
            continue
        src = r.matched_corpus_source or "unknown"
        row = by_source.setdefault(src, {"source": src, "matched_words": 0, "sentences": 0})
        row["matched_words"] += _word_count(r.sentence)
        row["sentences"] += 1
    rows = list(by_source.values())
    for row in rows:
        row["coverage"] = round(row["matched_words"] / total, 4)
    rows.sort(key=lambda r: r["coverage"], reverse=True)
    return rows


def _exclusion_reason(result: LocalSentenceResult) -> Optional[str]:
    if result.boilerplate:
        return "common_phrase"
    if result.quoted:
        return "quoted"
    if result.cited:
        return "cited"
    return None


def select_web_candidates(
    local_results: Sequence[LocalSentenceResult],
    score_threshold: float = config.WEB_VERIFY_SCORE_THRESHOLD,
    top_k: int = config.WEB_VERIFY_TOP_K,
    max_calls: int = config.WEB_VERIFY_MAX_CALLS,
) -> List[LocalSentenceResult]:
    """
    Pick the top-K Stage-1 hits for Stage 2. Returns [] → Stage 2 skipped.
    Only sentences that actually count as matches are worth a web call.
    """
    eligible = [
        r for r in local_results
        if r.counts_toward_score and r.local_suspicion_score > score_threshold
    ]
    eligible.sort(key=lambda r: r.local_suspicion_score, reverse=True)
    limit = min(top_k, max_calls)
    return eligible[:limit]


# ── Report building ──────────────────────────────────────────────────────────

def _local_to_flagged_dict(result: LocalSentenceResult) -> Dict[str, Any]:
    match_type = result.match_type
    if match_type not in ("exact", "semantic", "both"):
        # Schema expects exact | semantic | both for flagged rows; derive from scores.
        if result.exact.score >= result.semantic.score:
            match_type = "exact"
        else:
            match_type = "semantic"

    return {
        "sentence": result.sentence,
        "chunk_id": result.chunk_id,
        "local_suspicion_score": round(result.local_suspicion_score, 4),
        "exact_score": round(result.exact.score, 4),
        "semantic_score": round(result.semantic.score, 4),
        "match_type": match_type,
        "matched_corpus_source": result.matched_corpus_source,
        "matched_text": result.matched_text,
        "web_verified": None,
        "web_source_url": None,
    }


def build_report(
    document_id: str,
    local_results: Sequence[LocalSentenceResult],
    web_by_chunk: Dict[str, WebVerifyResult],
    corpus_size: int,
    web_checks_performed: int,
) -> Dict[str, Any]:
    """
    Assemble the structured JSON plagiarism report.

    ``flagged_sentences`` holds only matches that count toward the score;
    ``excluded_sentences`` holds matches skipped as common phrasing, quotes or
    cited text (kept for transparency, not counted).
    """
    flagged: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    for result in local_results:
        if not result.flagged:
            continue
        row = _local_to_flagged_dict(result)
        reason = _exclusion_reason(result)
        if reason is not None:
            row["excluded_reason"] = reason
            excluded.append(row)
            continue
        web = web_by_chunk.get(result.chunk_id)
        if web is not None:
            row["web_verified"] = web.web_verified
            row["web_source_url"] = web.web_source_url
            if web.note and web.web_verified is None:
                row["web_note"] = web.note
        flagged.append(row)

    # Highest suspicion first in the report.
    flagged.sort(key=lambda r: r["local_suspicion_score"], reverse=True)
    excluded.sort(key=lambda r: r["local_suspicion_score"], reverse=True)

    return {
        "document_id": document_id,
        # Similarity index: share of checked words that match the corpus.
        "overall_plagiarism_score": overall_plagiarism_score(local_results),
        "mean_match_similarity": mean_match_similarity(local_results),
        "source_breakdown": source_breakdown(local_results),
        "flagged_sentences": flagged,
        "excluded_sentences": excluded,
        "corpus_size": corpus_size,
        "sentences_checked": len(local_results),
        "words_checked": sum(_word_count(r.sentence) for r in local_results),
        "web_checks_performed": web_checks_performed,
    }


# ── Public async API (FastAPI-compatible) ────────────────────────────────────

async def detect_plagiarism(
    document: Union[str, Sequence[Union[str, Dict[str, Any]]]],
    document_id: str = "unknown",
    corpus: Optional[CorpusIndex] = None,
    corpus_dir: Optional[Path] = None,
    force_rebuild_index: bool = False,
    enable_web_verify: bool = True,
) -> Dict[str, Any]:
    """
    Run the full two-stage hybrid plagiarism detector.

    Safe to await from a FastAPI route. Heavy CPU/embedding work is offloaded to
    a thread so the event loop stays responsive.

    Args:
        document: Parsed text — string, list of strings, or chunk dicts.
        document_id: Caller-supplied id for the report.
        corpus: Optional pre-loaded CorpusIndex (preferred in long-running servers).
        corpus_dir: Override local corpus folder when building the index.
        force_rebuild_index: Rebuild MinHash/FAISS caches.
        enable_web_verify: If False, skip Stage 2 even when scores qualify.

    Returns:
        Structured plagiarism report dict (JSON-serialisable).

    Raises:
        ValueError: Empty document or empty/missing corpus (clear message).
    """
    chunks = normalize_chunks(document)
    if not chunks:
        raise ValueError(
            "Empty document: no sentences/chunks to check. "
            "Pass non-empty parsed text from the ingestion pipeline."
        )

    checkable = filter_checkable_sentences(chunks)
    if not checkable:
        raise ValueError(
            f"Document has no sentences with at least {config.MIN_SENTENCE_WORDS} "
            "words; nothing to check for plagiarism."
        )

    def _run_sync() -> Dict[str, Any]:
        nonlocal corpus
        if corpus is None:
            corpus = build_corpus_index(
                corpus_dir=corpus_dir,
                force_rebuild=force_rebuild_index,
            )

        if corpus.size == 0:
            raise ValueError("Loaded corpus is empty.")

        local_results = analyze_document_local(checkable, corpus)

        web_by_chunk: Dict[str, WebVerifyResult] = {}
        web_checks = 0

        if enable_web_verify:
            candidates = select_web_candidates(local_results)
            for cand in candidates:
                # try/except inside verify_sentence_on_web — never crashes pipeline.
                web_by_chunk[cand.chunk_id] = verify_sentence_on_web(cand.sentence)
                web_checks += 1

        return build_report(
            document_id=document_id,
            local_results=local_results,
            web_by_chunk=web_by_chunk,
            corpus_size=corpus.size,
            web_checks_performed=web_checks,
        )

    return await asyncio.to_thread(_run_sync)


def detect_plagiarism_sync(
    document: Union[str, Sequence[Union[str, Dict[str, Any]]]],
    document_id: str = "unknown",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Synchronous wrapper for CLI / unit tests."""
    return asyncio.run(detect_plagiarism(document, document_id=document_id, **kwargs))


# ── CLI entry point ──────────────────────────────────────────────────────────

def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Formatify hybrid plagiarism detector (local corpus + selective web)."
    )
    parser.add_argument(
        "--text",
        type=str,
        help="Document text to check (or omit to use --file / stdin sample).",
    )
    parser.add_argument("--file", type=str, help="Path to a .txt document to check.")
    parser.add_argument("--document-id", type=str, default="cli_document")
    parser.add_argument(
        "--corpus-dir",
        type=str,
        default=None,
        help="Folder of .txt reference files (default: plagiarism/sample_corpus).",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Force rebuild of MinHashLSH + FAISS caches.",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Disable Stage 2 Google Custom Search.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON report.",
    )
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        # Demo text: overlaps with sample_corpus intentionally.
        text = (
            "Machine learning is a subset of artificial intelligence that enables "
            "systems to learn and improve from experience without being explicitly "
            "programmed. Deep learning models use multiple layers of neural networks "
            "to extract hierarchical features from raw data. This completely original "
            "sentence about gardening and soil moisture should not match anything."
        )

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else None

    try:
        report = detect_plagiarism_sync(
            text,
            document_id=args.document_id,
            corpus_dir=corpus_dir,
            force_rebuild_index=args.rebuild_index,
            enable_web_verify=not args.no_web,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    indent = 2 if args.pretty else None
    print(json.dumps(report, indent=indent, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
