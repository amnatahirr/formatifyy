"""
aggregator.py — Result aggregator for Formatify.

Merges all batch results, deduplicates overlap issues, and computes
summary statistics matching the JSON contract expected by the Flutter frontend.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from models import AnalysisReport, DocumentInfo, Issue, Stats, DocumentModel


def aggregate(
    raw_issues: List[Dict[str, Any]],
    doc: DocumentModel,
    total_batches: int,
) -> AnalysisReport:
    """
    Merge raw issue dicts from the dispatcher into a deduplicated
    AnalysisReport with computed statistics.

    Deduplication key:
      - For paragraphs: (function, paragraph_id)
      - For images: (function, image_id)
    """
    seen: Set[str] = set()
    unique_issues: List[Issue] = []

    # Track per-function scores for averaging
    compliance_scores: List[float] = []
    risk_scores: List[float] = []

    for raw in raw_issues:
        # Build dedup key
        func = raw.get("function", "")
        pid = raw.get("paragraph_id", "")
        iid = raw.get("image_id", "")

        if pid:
            dedup_key = f"{func}:{pid}"
        elif iid:
            dedup_key = f"{func}:{iid}"
        else:
            # No ID — use reason hash as fallback
            dedup_key = f"{func}:{hash(raw.get('reason', ''))}"

        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        # Collect averaging data from private keys
        if "_compliance_score" in raw:
            compliance_scores.append(float(raw["_compliance_score"]))
        if "_risk_score" in raw:
            risk_scores.append(float(raw["_risk_score"]))

        # Strip private keys before creating the Issue
        clean = {k: v for k, v in raw.items() if not k.startswith("_")}
        unique_issues.append(Issue(**clean))

    # ── Compute statistics ────────────────────────────────────────────────────
    stats = Stats(
        total_issues=len(unique_issues),
        grammar_issues=sum(1 for i in unique_issues if i.function == "grammar"),
        formatting_issues=sum(1 for i in unique_issues if i.function == "formatting"),
        image_ethics_issues=sum(1 for i in unique_issues if i.function == "image_ethics"),
        image_relevance_issues=sum(1 for i in unique_issues if i.function == "image_relevance"),
        para_relevance_issues=sum(1 for i in unique_issues if i.function == "para_relevance"),
        plagiarism_issues=sum(1 for i in unique_issues if i.function == "plagiarism"),
        major_issues=sum(1 for i in unique_issues if i.severity == "major"),
        minor_issues=sum(1 for i in unique_issues if i.severity == "minor"),
        avg_formatting_compliance=round(
            sum(compliance_scores) / len(compliance_scores), 1
        ) if compliance_scores else 100.0,
        avg_plagiarism_risk=round(
            sum(risk_scores) / len(risk_scores), 1
        ) if risk_scores else 0.0,
    )

    doc_info = DocumentInfo(
        filename=doc.filename,
        total_pages=doc.total_pages,
        total_paragraphs=len(doc.paragraphs),
        total_images=len(doc.images),
        total_batches=total_batches,
    )

    return AnalysisReport(
        issues=unique_issues,
        stats=stats,
        document_info=doc_info,
    )
