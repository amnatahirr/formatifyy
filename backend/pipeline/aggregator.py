"""
aggregator.py — Result aggregator for Formatify.

Merges all batch results, deduplicates overlap issues, and computes
summary statistics matching the JSON contract expected by the Flutter frontend.

Also runs a list-coverage validation pass: any run of 3+ consecutive
paragraphs sharing an opening grammatical pattern that was NOT converted
to a list is flagged for review (never silently guessed).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

from models import AnalysisReport, DocumentInfo, Issue, Stats, DocumentModel


def aggregate(
    raw_issues: List[Dict[str, Any]],
    doc: DocumentModel,
    total_batches: int,
    *,
    list_validation_flags: Optional[List[Dict[str, Any]]] = None,
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
        itype = raw.get("type", "")

        if pid:
            dedup_key = f"{func}:{itype}:{pid}"
        elif iid:
            dedup_key = f"{func}:{iid}"
        else:
            # No ID — use reason hash as fallback
            dedup_key = f"{func}:{itype}:{hash(raw.get('reason', ''))}"

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
        none_keys = [k for k, v in clean.items() if v is None]
        if none_keys:
            print(
                f"[aggregator] WARNING: {func}/{itype} returned None for "
                f"{none_keys}, using defaults"
            )
            for k in none_keys:
                clean.pop(k)
        unique_issues.append(Issue(**clean))

    # ── Aggregator list self-check ────────────────────────────────────────────
    flags = list_validation_flags
    if flags is None:
        flags = _run_list_validation(doc, unique_issues)

    for flag in flags or []:
        print(
            f"[aggregator] LIST REVIEW FLAG: pattern={flag.get('pattern')} "
            f"count={flag.get('count')} ids={flag.get('paragraph_ids')} "
            f"— {flag.get('reason')}"
        )
        pid = (flag.get("paragraph_ids") or [""])[0]
        dedup_key = f"formatting:unconverted_parallel_list:{pid}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        unique_issues.append(Issue(
            function="formatting",
            type="unconverted_parallel_list",
            severity="minor",
            paragraph_id=pid,
            page=0,
            reason=flag.get("reason") or "Parallel paragraphs need list review.",
            suggestion="Review and convert this parallel run into a Word bullet list.",
            explanation=(
                f"Auto-validation: {flag.get('count')} consecutive paragraphs "
                f"share '{flag.get('pattern')}' openings but were not converted."
            ),
            original="; ".join(flag.get("preview") or []),
            source="aggregator_list_validation",
            needs_review=True,
            list_detection=flag.get("pattern"),
            para_indices=flag.get("indices") or [],
        ))

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


def _run_list_validation(
    doc: DocumentModel,
    issues: Sequence[Issue],
) -> List[Dict[str, Any]]:
    """Flag 3+ parallel opening runs that were not already marked as lists."""
    try:
        from docx_tools.list_detection import detect_list_groups, find_unconverted_parallel_runs
    except Exception as exc:
        print(f"[aggregator] list_detection import failed: {exc}")
        return []

    groups = detect_list_groups(doc.paragraphs)
    # Indices already raised as missing_bullets / list_formatting count as covered
    covered: Set[int] = set()
    for g in groups:
        covered.update(g.indices)
        print(
            f"[aggregator] list auto-detected: {g.detection} "
            f"-> {g.paragraph_ids}"
        )
    for iss in issues:
        for idx in getattr(iss, "para_indices", None) or []:
            try:
                covered.add(int(idx))
            except (TypeError, ValueError):
                pass
        if iss.type in ("missing_bullets", "list_formatting") and iss.paragraph_id:
            pid = iss.paragraph_id
            if pid.startswith("p") and pid[1:].isdigit():
                covered.add(int(pid[1:]))

    return find_unconverted_parallel_runs(
        doc.paragraphs,
        min_run=3,
        treated_as_list_indices=covered,
    )
