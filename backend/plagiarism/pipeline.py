"""
plagiarism/pipeline.py — Bridge hybrid corpus detector → Formatify Issue dicts.

Runs once per document (not per batch) so the full text is checked against the
local FYP corpus. Safe to await from FastAPI; failures return [] and never abort
the rest of analysis.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models import DocumentModel
from plagiarism import config
from plagiarism.corpus_index import split_into_sentences, tokenize
from plagiarism.detector import detect_plagiarism


# Process-wide corpus index handle (built lazily on first analysis).
_CORPUS_INDEX = None
_CORPUS_LOAD_ERROR: Optional[str] = None


def corpus_plagiarism_enabled() -> bool:
    """Master switch — default on when a non-empty corpus dir is configured."""
    flag = os.getenv("PLAGIARISM_USE_CORPUS", "true").strip().lower()
    return flag in ("1", "true", "yes", "on")


def web_verify_enabled() -> bool:
    flag = os.getenv("PLAGIARISM_ENABLE_WEB", "false").strip().lower()
    return flag in ("1", "true", "yes", "on")


def get_or_build_corpus_index(force_rebuild: bool = False):
    """Lazy singleton CorpusIndex for the running API process."""
    global _CORPUS_INDEX, _CORPUS_LOAD_ERROR
    if force_rebuild:
        _CORPUS_INDEX = None
        _CORPUS_LOAD_ERROR = None
    if _CORPUS_INDEX is not None:
        return _CORPUS_INDEX
    if _CORPUS_LOAD_ERROR and not force_rebuild:
        raise ValueError(_CORPUS_LOAD_ERROR)

    from plagiarism.corpus_index import build_corpus_index

    try:
        _CORPUS_INDEX = build_corpus_index(
            corpus_dir=config.CORPUS_DIR,
            force_rebuild=force_rebuild,
        )
        _CORPUS_LOAD_ERROR = None
        print(
            f"[plagiarism] corpus ready: {_CORPUS_INDEX.size} docs, "
            f"{_CORPUS_INDEX.sentence_count} sentences "
            f"(dir={config.CORPUS_DIR})"
        )
        return _CORPUS_INDEX
    except Exception as exc:
        _CORPUS_LOAD_ERROR = str(exc)
        raise


def document_to_chunks(doc: DocumentModel) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, Any]]]:
    """
    Split body paragraphs into sentence chunks for the detector.

    Returns:
      chunks: [{text, chunk_id}, ...]
      meta: chunk_id → {paragraph_id, page, heading_context}
    """
    chunks: List[Dict[str, str]] = []
    meta: Dict[str, Dict[str, Any]] = {}

    for para in doc.paragraphs:
        style = (para.style or "Normal").lower()
        # Skip obvious headings; body + caption-like styles are checked.
        if style.startswith("heading"):
            continue
        text = (para.text or "").strip()
        if not text:
            continue

        sentences = split_into_sentences(text)
        if not sentences:
            sentences = [text]

        for i, sentence in enumerate(sentences):
            if len(tokenize(sentence)) < config.MIN_SENTENCE_WORDS:
                continue
            chunk_id = f"{para.paragraph_id}_s{i}"
            chunks.append({"text": sentence, "chunk_id": chunk_id})
            meta[chunk_id] = {
                "paragraph_id": para.paragraph_id,
                "page": para.page_number,
                "heading_context": para.heading_context or "",
            }

    return chunks, meta


def report_to_issues(
    report: Dict[str, Any],
    chunk_meta: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Map detector flagged_sentences → Issue-shaped dicts for the aggregator."""
    issues: List[Dict[str, Any]] = []
    overall = float(report.get("overall_plagiarism_score") or 0.0)

    for row in report.get("flagged_sentences") or []:
        chunk_id = str(row.get("chunk_id") or "")
        info = chunk_meta.get(chunk_id, {})
        score = float(row.get("local_suspicion_score") or 0.0)
        risk = int(round(score * 100))
        match_type = str(row.get("match_type") or "semantic")
        source = row.get("matched_corpus_source") or "unknown FYP report"
        sentence = str(row.get("sentence") or "")
        web_verified = row.get("web_verified")
        web_url = row.get("web_source_url")

        reason = (
            f"This sentence closely matches previous FYP report '{source}' "
            f"({match_type} similarity {risk}%)."
        )
        suggestion = (
            "Rewrite in your own words and cite the original source if you reused ideas."
        )
        explanation = reason
        if web_verified:
            explanation += f" Also verified on the web: {web_url or 'match found'}."

        severity = "major" if risk >= 70 else "minor"
        issue_type = (
            "corpus_exact_match"
            if match_type in ("exact", "both")
            else "corpus_semantic_match"
        )

        issues.append({
            "function": "plagiarism",
            "type": issue_type,
            "severity": severity,
            "paragraph_id": info.get("paragraph_id", ""),
            "image_id": "",
            "page": int(info.get("page") or 0),
            "reason": reason,
            "suggestion": suggestion,
            "explanation": explanation,
            "original": sentence[:500],
            "current_heading": info.get("heading_context", ""),
            "content_belongs_to": "",
            "text_preview": sentence[:160],
            "verdict": f"match={match_type}; corpus={source}; score={score:.3f}",
            "confidence": float(risk),
            "similarity": score,
            "source": "fyp_corpus",
            "surrounding_text": str(source),
            "_risk_score": risk,
            "_overall_risk": int(round(overall * 100)),
        })

    return issues


async def check_document_against_fyp_corpus(
    doc: DocumentModel,
    document_id: str = "unknown",
) -> List[Dict[str, Any]]:
    """
    Full-document corpus plagiarism check.

    Returns Issue dicts, or [] if disabled / corpus missing / no matches.
    Never raises to the analysis caller.
    """
    if not corpus_plagiarism_enabled():
        return []

    chunks, meta = document_to_chunks(doc)
    if not chunks:
        print("[plagiarism] no checkable sentences in document")
        return []

    try:
        corpus = get_or_build_corpus_index()
    except Exception as exc:
        print(
            f"[plagiarism] corpus unavailable — skipping corpus check: {exc}\n"
            f"  Put FYP reports in {config.CORPUS_DIR} (or run "
            f"`python -m plagiarism.ingest_corpus`) then restart the server."
        )
        return []

    try:
        report = await detect_plagiarism(
            chunks,
            document_id=document_id,
            corpus=corpus,
            enable_web_verify=web_verify_enabled(),
        )
    except ValueError as exc:
        print(f"[plagiarism] detector skipped: {exc}")
        return []
    except Exception as exc:
        print(f"[plagiarism] detector error: {exc}")
        return []

    issues = report_to_issues(report, meta)
    print(
        f"[plagiarism] corpus check done: score={report.get('overall_plagiarism_score')} "
        f"flagged={len(issues)} / checked={report.get('sentences_checked')} "
        f"corpus_docs={report.get('corpus_size')}"
    )
    return issues
