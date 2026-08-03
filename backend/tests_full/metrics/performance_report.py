"""
Performance metrics — real pipeline microbenches + report persistence.

Each benchmark documents the EXACT module.function exercised. Nothing here
should call a MagicMock for the timed region.

Standalone:
  cd backend && python -m tests_full.metrics.performance_report
"""
from __future__ import annotations

import io
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "performance_report.json"


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT.parent),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def measure_call(fn: Callable, *args, rounds: int = 5, **kwargs) -> Dict[str, Any]:
    import psutil

    proc = psutil.Process(os.getpid())
    times: List[float] = []
    peak_mem = 0
    peak_rss = 0
    proc.cpu_percent(interval=None)
    result = None
    for _ in range(rounds):
        rss_before = proc.memory_info().rss
        tracemalloc.start()
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        times.append(elapsed)
        peak_mem = max(peak_mem, peak)
        peak_rss = max(peak_rss, proc.memory_info().rss, rss_before)
    cpu = proc.cpu_percent(interval=0.05)
    times_sorted = sorted(times)
    p95_idx = min(len(times_sorted) - 1, max(0, int(round(0.95 * (len(times_sorted) - 1)))))
    return {
        "rounds": rounds,
        "min_s": round(min(times), 6),
        "max_s": round(max(times), 6),
        "mean_s": round(statistics.mean(times), 6),
        "median_s": round(statistics.median(times), 6),
        "stddev_s": round(statistics.pstdev(times), 6) if len(times) > 1 else 0.0,
        "p95_s": round(times_sorted[p95_idx], 6),
        "peak_memory_mb": round(peak_mem / (1024 * 1024), 3),
        "peak_rss_mb": round(peak_rss / (1024 * 1024), 3),
        "cpu_percent": cpu,
        "_last_result": result,
    }


def load_history() -> List[dict]:
    if not RESULTS_PATH.exists():
        return []
    try:
        data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def append_result(row: dict) -> dict:
    row = {
        **row,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": _git_commit(),
    }
    # strip non-serializable
    row.pop("_last_result", None)
    hist = load_history()
    hist.append(row)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    return row


def warn_if_regression(test_name: str, mean_s: float, factor: float = 2.0) -> Optional[str]:
    hist = [h for h in load_history() if h.get("test") == test_name and h.get("mean_s")]
    if len(hist) < 1:
        return None
    # compare against previous (before this append) — caller should warn before append
    prev = float(hist[-1]["mean_s"])
    if prev > 0 and mean_s > factor * prev:
        return f"WARN: {test_name} mean {mean_s:.4f}s is >{factor}x previous {prev:.4f}s"
    return None


def print_table(rows: List[dict]) -> None:
    if not rows:
        print("No performance results.")
        return
    try:
        from tabulate import tabulate

        table = [
            [
                r.get("test"),
                r.get("real_path"),
                r.get("mean_s"),
                r.get("median_s"),
                r.get("p95_s"),
                r.get("peak_memory_mb"),
                r.get("cpu_percent"),
                r.get("throughput_pages_per_s")
                or r.get("throughput_docs_per_min")
                or "",
                r.get("is_real_pipeline"),
            ]
            for r in rows
        ]
        print(
            tabulate(
                table,
                headers=[
                    "test",
                    "real_path",
                    "mean_s",
                    "median",
                    "p95",
                    "mem_MB",
                    "cpu%",
                    "throughput",
                    "REAL?",
                ],
                tablefmt="github",
            )
        )
    except Exception:
        for r in rows:
            print(r)


def _make_doc(pages: int = 20, paras_per_page: int = 3):
    from models import DocumentModel, ParagraphBlock

    paragraphs = [
        ParagraphBlock(
            paragraph_id=f"page{pg}-para{i}",
            page_number=pg,
            text=(
                f"Synthetic academic paragraph {pg}.{i} discussing methodology, "
                f"evaluation metrics, and related work implications. " * 3
            ),
        )
        for pg in range(1, pages + 1)
        for i in range(paras_per_page)
    ]
    return DocumentModel(
        filename="perf_synth.txt",
        total_pages=pages,
        paragraphs=paragraphs,
        images=[],
    )


def _make_docx(path: str, pages_worth: int = 8) -> str:
    from docx import Document

    doc = Document()
    for i in range(1, pages_worth + 1):
        doc.add_heading(f"Section {i}", level=1)
        for j in range(4):
            doc.add_paragraph(
                f"Body paragraph {i}.{j} with enough words to exercise the "
                f"parser, reformatter, and merge assembler pathways in tests."
            )
    doc.save(path)
    return path


def bench_e2e_full_analyze_with_llm(rounds: int = 1) -> Dict[str, Any]:
    """
    Full analyze path INCLUDING real LLM agents (grammar/formatting/images/…).
    Same core as main._run_analysis via production_runners.run_full_analyze_pipeline.
    Requires GEMINI_API_KEY or ANTHROPIC_API_KEY — raises LLMUnavailableError otherwise.
    """
    import asyncio

    from tests_full.metrics.production_runners import (
        LLMUnavailableError,
        llm_keys_status,
        require_llm_client,
        run_full_analyze_pipeline,
    )

    # Fail loud before timing if keys missing
    require_llm_client()
    keys = llm_keys_status()

    with tempfile.TemporaryDirectory() as td:
        docx_in = os.path.join(td, "e2e_full.docx")
        _make_docx(docx_in, pages_worth=6)
        template = {
            "name": "perf_full_analyze",
            "required_sections": ["Section 1", "Section 2", "Section 3"],
            "formatting_rules": {"fonts": {"body": "Times New Roman"}},
            "markdown_rules": "",
        }

        def _once():
            return asyncio.run(
                run_full_analyze_pipeline(docx_in, "e2e_full.docx", template)
            )

        stats = measure_call(_once, rounds=max(1, rounds))
        last = stats.pop("_last_result", None) or {}
        stats.update(
            {
                "test": "e2e_full_analyze_with_llm_agents",
                "real_path": (
                    "parser.parse_file -> batcher.create_batches -> "
                    "dispatcher.dispatch_all (check_grammar, check_formatting, "
                    "check_images_combined, check_para_relevance) || "
                    "plagiarism.pipeline.check_document_against_fyp_corpus -> "
                    "aggregator.aggregate -> reformatter.reformat_document"
                ),
                "is_real_pipeline": True,
                "mocked": False,
                "llm_included": True,
                "llm_keys": keys,
                "provider": last.get("provider"),
                "pipeline_meta": {
                    k: last.get(k)
                    for k in (
                        "pages",
                        "paragraphs",
                        "batches",
                        "issues",
                        "token_usage",
                        "cost_estimate_usd",
                        "cost_note",
                        "functions_invoked",
                        "reformat_error",
                    )
                },
                "sanity_note": (
                    "REAL full analyze with LLM agents. "
                    "Token/cost fields are None unless adapter exposes usage."
                ),
            }
        )
        return stats


def run_all_benchmarks(rounds: int = 5) -> List[dict]:
    """
    Run REAL pipeline benches. Returns rows ready to print/persist.
    Does NOT include slow LLM e2e — call bench_e2e_full_analyze_with_llm separately.
    """
    from aggregator import aggregate
    from batcher import create_batches
    from parser import parse_file, parse_text
    from plagiarism.web_verify import word_jaccard
    from reformatter import reformat_document
    from list_detection import detect_list_groups
    from models import AnalysisReport, Stats
    from vc.merge import assemble_merged_docx
    from vc.utils import word_overlap_ratio

    rows: List[dict] = []
    doc = _make_doc(24, 3)

    # 1) batcher
    stats = measure_call(lambda: create_batches(doc, batch_size=4, overlap=1), rounds=rounds)
    stats.update(
        {
            "test": "batcher_24_pages",
            "real_path": "batcher.create_batches",
            "is_real_pipeline": True,
            "mocked": False,
            "throughput_pages_per_s": round(24 / stats["mean_s"], 2) if stats["mean_s"] else 0,
        }
    )
    rows.append(stats)

    # 2) aggregator
    raw = [
        {
            "function": "grammar",
            "type": "spelling",
            "paragraph_id": f"page{i}-para0",
            "severity": "minor",
            "reason": "x",
        }
        for i in range(1, 25)
    ] * 2
    stats = measure_call(
        lambda: aggregate(raw, doc, total_batches=6, list_validation_flags=[]),
        rounds=rounds,
    )
    stats.update(
        {
            "test": "aggregator_dedup_24",
            "real_path": "aggregator.aggregate",
            "is_real_pipeline": True,
            "mocked": False,
        }
    )
    rows.append(stats)

    # 3) parse_text large
    blob = "\n\n".join(
        f"Section {i}\n\nBody paragraph number {i} with filler content about evaluation."
        for i in range(1, 61)
    )
    stats = measure_call(lambda: parse_text(blob), rounds=rounds)
    stats.update(
        {
            "test": "parser_parse_text_60",
            "real_path": "parser.parse_text",
            "is_real_pipeline": True,
            "mocked": False,
            "throughput_docs_per_min": round(60 / stats["mean_s"], 2) if stats["mean_s"] else 0,
        }
    )
    rows.append(stats)

    # 4) parse_file DOCX
    with tempfile.TemporaryDirectory() as td:
        docx_in = os.path.join(td, "in.docx")
        _make_docx(docx_in, pages_worth=10)

        def _parse():
            return parse_file(docx_in, "in.docx")

        stats = measure_call(_parse, rounds=max(3, rounds - 1))
        stats.update(
            {
                "test": "parser_parse_file_docx_10",
                "real_path": "parser.parse_file",
                "is_real_pipeline": True,
                "mocked": False,
            }
        )
        rows.append(stats)

        # 5) reformat_document (REAL python-docx rewrite)
        report = AnalysisReport(issues=[], stats=Stats())
        out_path = os.path.join(td, "out.docx")

        def _reformat():
            return reformat_document(
                docx_in,
                out_path,
                report,
                {"fonts": {"body": "Times New Roman"}, "margins": {}},
                required_sections=[
                    {"title": "Section 1", "level": 1},
                    {"title": "Section 2", "level": 1},
                ],
            )

        stats = measure_call(_reformat, rounds=max(3, rounds - 1))
        # Sanity: reformatting a 10-section DOCX should not be sub-millisecond
        stats.update(
            {
                "test": "reformatter_reformat_document",
                "real_path": "reformatter.reformat_document",
                "is_real_pipeline": True,
                "mocked": False,
                "sanity_note": "expect >>1ms on real DOCX I/O",
            }
        )
        rows.append(stats)

        # 6) VC merge assemble
        sections = [
            {
                "section_id": f"s{i}",
                "section_name": f"Section {i}",
                "heading_level": 1,
                "template_order": i,
            }
            for i in range(1, 6)
        ]
        content = {f"s{i}": f"Merged content for section {i}. " * 40 for i in range(1, 6)}
        merge_out = os.path.join(td, "merged.docx")

        def _merge():
            return assemble_merged_docx(
                sections, content, merge_out, template_id=1, section_images=None
            )

        stats = measure_call(_merge, rounds=max(3, rounds - 1))
        stats.update(
            {
                "test": "vc_assemble_merged_docx",
                "real_path": "vc.merge.assemble_merged_docx",
                "is_real_pipeline": True,
                "mocked": False,
            }
        )
        rows.append(stats)

    # 7) plagiarism jaccard on long strings
    a = ("quantum entanglement laboratory controlled noise particles " * 80).strip()
    b = ("quantum entanglement laboratory managed interference particles " * 80).strip()
    stats = measure_call(lambda: word_jaccard(a, b), rounds=rounds)
    stats.update(
        {
            "test": "plagiarism_word_jaccard_long",
            "real_path": "plagiarism.web_verify.word_jaccard",
            "is_real_pipeline": True,
            "mocked": False,
        }
    )
    rows.append(stats)

    # 8) list detection on many blocks
    blocks = []
    blocks.append(
        {"paragraph_id": "t0", "text": "The system requires the following:", "style": "Normal", "index": 0}
    )
    for i in range(1, 31):
        blocks.append(
            {
                "paragraph_id": f"t{i}",
                "text": f"- Capability item number {i} for detection throughput.",
                "style": "Normal",
                "index": i,
            }
        )
    stats = measure_call(lambda: detect_list_groups(blocks), rounds=rounds)
    stats.update(
        {
            "test": "list_detection_30_items",
            "real_path": "list_detection.detect_list_groups",
            "is_real_pipeline": True,
            "mocked": False,
        }
    )
    rows.append(stats)

    # 9) e2e skeleton: parse → batch → aggregate → reformat (NO LLM agents)
    with tempfile.TemporaryDirectory() as td:
        docx_in = os.path.join(td, "e2e.docx")
        _make_docx(docx_in, pages_worth=6)
        out_path = os.path.join(td, "e2e_out.docx")

        def _e2e():
            parsed = parse_file(docx_in, "e2e.docx")
            batches = create_batches(parsed, batch_size=4, overlap=1)
            # Synthetic issues stand in for LLM agents — clearly labeled
            fake_issues = [
                {
                    "function": "grammar",
                    "type": "spelling",
                    "paragraph_id": parsed.paragraphs[0].paragraph_id
                    if parsed.paragraphs
                    else "p0",
                    "severity": "minor",
                    "reason": "synthetic",
                }
            ]
            report = aggregate(
                fake_issues, parsed, total_batches=len(batches), list_validation_flags=[]
            )
            reformat_document(
                docx_in,
                out_path,
                report,
                {"fonts": {"body": "Times New Roman"}},
                required_sections=None,
            )
            return {
                "pages": parsed.total_pages,
                "batches": len(batches),
                "issues": report.stats.total_issues,
            }

        stats = measure_call(_e2e, rounds=max(3, rounds - 1))
        stats.update(
            {
                "test": "e2e_parse_batch_aggregate_reformat",
                "real_path": (
                    "parser.parse_file → batcher.create_batches → "
                    "aggregator.aggregate → reformatter.reformat_document"
                ),
                "is_real_pipeline": True,
                "mocked": "LLM agents NOT invoked; synthetic issue list only",
                "sanity_note": (
                    "NOT full analyze with grammar/formatting/image/plagiarism LLMs. "
                    "Those require API keys and dominate wall-clock."
                ),
            }
        )
        # Flag suspiciously fast e2e (<50ms) as likely buggy
        if stats["mean_s"] < 0.05:
            stats["suspicious_fast"] = True
            stats["sanity_note"] += " | SUSPICIOUS: mean < 50ms for DOCX e2e"
        rows.append(stats)

    # 10) vc overlap util
    stats = measure_call(
        lambda: word_overlap_ratio("alpha beta gamma " * 50, "alpha beta zeta " * 50),
        rounds=rounds,
    )
    stats.update(
        {
            "test": "vc_word_overlap_ratio",
            "real_path": "vc.utils.word_overlap_ratio",
            "is_real_pipeline": True,
            "mocked": False,
        }
    )
    rows.append(stats)

    return rows


def main() -> int:
    print("=== Running REAL performance benchmarks ===")
    rows = run_all_benchmarks(rounds=5)
    clean = []
    for r in rows:
        warn = warn_if_regression(r["test"], float(r["mean_s"]))
        if warn:
            print(warn)
        stored = append_result({k: v for k, v in r.items() if k != "_last_result"})
        clean.append(stored)
    print_table(clean)
    print(f"\nAppended {len(clean)} rows → {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
