"""
Pytest wrappers for accuracy + performance metrics.

Delegates to hardened logic in metrics/accuracy_report.py and
metrics/performance_report.py (per-fixture ci_min_f1, real pipelines).
"""
from __future__ import annotations

import pytest

from tests_full.metrics.accuracy_report import (
    SchemaMismatchError,
    THRESHOLDS,
    evaluate_all,
    gate_failures,
    persist_scores,
    print_table,
)
from tests_full.metrics.performance_report import (
    append_result,
    measure_call,
    run_all_benchmarks,
    warn_if_regression,
)


@pytest.mark.accuracy
@pytest.mark.p1
@pytest.mark.pipeline
def test_accuracy_all_ground_truth_fixtures(acc_recorder):
    try:
        scores = evaluate_all()
    except SchemaMismatchError:
        raise
    assert scores, "No ground_truth fixtures scored"
    print("\n=== Accuracy per fixture ===")
    print_table(scores)
    persist_scores(scores)
    for s in scores:
        acc_recorder(s.to_dict())
    fails = gate_failures(scores)
    assert not fails, "Accuracy CI gate failures:\n" + "\n".join(fails)


@pytest.mark.accuracy
@pytest.mark.p1
def test_accuracy_thresholds_documented():
    assert THRESHOLDS["list_detection"] >= 0.55
    assert THRESHOLDS["default"] >= 0.50


@pytest.mark.accuracy
@pytest.mark.p1
def test_accuracy_schema_guard_refuses_silent_empty():
    from tests_full.metrics.accuracy_report import _assert_schema

    with pytest.raises(SchemaMismatchError, match="never invoked"):
        _assert_schema([], kind="issues", fixture="x", detector_invoked=False)


@pytest.mark.performance
@pytest.mark.pipeline
@pytest.mark.p2
def test_performance_real_pipelines(benchmark, perf_recorder):
    from batcher import create_batches
    from tests_full.metrics.performance_report import _make_doc

    doc = _make_doc(16, 2)
    benchmark(lambda: create_batches(doc, batch_size=4, overlap=1))

    rows = run_all_benchmarks(rounds=4)
    for r in rows:
        payload = {k: v for k, v in r.items() if k != "_last_result"}
        warn = warn_if_regression(payload["test"], float(payload["mean_s"]))
        if warn:
            print(warn)
        if payload.get("test") == "e2e_parse_batch_aggregate_reformat":
            assert payload["mean_s"] >= 0.05, (
                f"e2e mean {payload['mean_s']}s < 50ms — not real DOCX I/O"
            )
        stored = append_result(payload)
        perf_recorder(stored)
        assert payload.get("is_real_pipeline") is True
        assert payload.get("real_path")


# Keep lightweight benches for regression smoke (also REAL, not mocked)
@pytest.mark.performance
@pytest.mark.p2
def test_performance_parse_text_throughput(perf_recorder):
    from parser import parse_text

    blob = "\n\n".join(
        [f"Section {i}\n\nBody paragraph number {i} with enough words." for i in range(50)]
    )
    stats = measure_call(lambda: parse_text(blob), rounds=5)
    stats["test"] = "perf_parse_text_50_sections"
    stats["real_path"] = "parser.parse_text"
    stats["is_real_pipeline"] = True
    stats["throughput_docs_per_min"] = (
        round(60 / stats["mean_s"], 2) if stats["mean_s"] else 0
    )
    stats.pop("_last_result", None)
    perf_recorder(append_result(stats))
    assert stats["mean_s"] > 0


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.pipeline
@pytest.mark.p3
def test_e2e_full_analyze_with_llm_agents(perf_recorder):
    """
    End-to-end /analyze core path WITH real LLM agents (not stubbed).

    Requires GEMINI_API_KEY or ANTHROPIC_API_KEY. Fails loudly if missing —
    does not skip or fake latency.

    Run:
      cd backend
      pytest -c tests_full/pytest.ini -m "performance and slow" -v
    """
    from tests_full.metrics.performance_report import bench_e2e_full_analyze_with_llm
    from tests_full.metrics.production_runners import LLMUnavailableError, llm_keys_status

    keys = llm_keys_status()
    if not keys["preferred"]:
        pytest.fail(
            "e2e_full_analyze_with_llm_agents requires GEMINI_API_KEY or "
            "ANTHROPIC_API_KEY in backend/.env — not set in this environment. "
            "Set one and re-run: pytest -c tests_full/pytest.ini -m \"performance and slow\" -v"
        )

    try:
        # rounds=3 → mean/median/p95 meaningful; single call still reports all three
        stats = bench_e2e_full_analyze_with_llm(rounds=3)
    except LLMUnavailableError as exc:
        pytest.fail(f"LLM unavailable for full e2e: {exc}")

    assert stats.get("llm_included") is True
    assert stats.get("mocked") is False
    assert stats["mean_s"] > 1.0, (
        f"Full LLM e2e mean={stats['mean_s']}s suspiciously fast — agents likely not called"
    )
    print(
        "\n=== e2e_full_analyze_with_llm_agents ===\n"
        f"provider={stats.get('provider')} keys={stats.get('llm_keys')}\n"
        f"mean={stats['mean_s']}s median={stats['median_s']}s p95={stats['p95_s']}s\n"
        f"peak_tracemalloc_mb={stats['peak_memory_mb']} peak_rss_mb={stats.get('peak_rss_mb')}\n"
        f"pipeline_meta={stats.get('pipeline_meta')}\n"
    )
    stored = append_result({k: v for k, v in stats.items() if k != "_last_result"})
    perf_recorder(stored)
