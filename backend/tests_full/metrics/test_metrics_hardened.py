"""
Pytest entrypoints for hardened accuracy + performance metrics.

Lives under metrics/ so functional tests_full/test_*.py stay untouched.
"""
from __future__ import annotations

import pytest

from tests_full.metrics.accuracy_report import (
    SchemaMismatchError,
    evaluate_all,
    gate_failures,
    persist_scores,
    print_table,
)
from tests_full.metrics.performance_report import (
    append_result,
    run_all_benchmarks,
    warn_if_regression,
)


@pytest.mark.accuracy
@pytest.mark.p1
@pytest.mark.pipeline
def test_accuracy_hardened_per_fixture(acc_recorder):
    """
    Alias of the canonical accuracy run in tests_full/test_metrics.py.
    Skipped here to avoid double LLM spend when `-m accuracy` selects both.
    """
    pytest.skip("Canonical run: tests_full/test_metrics.py::test_accuracy_all_ground_truth_fixtures")


@pytest.mark.accuracy
@pytest.mark.p1
def test_accuracy_schema_guard_refuses_silent_empty():
    """Detector-never-invoked must raise SchemaMismatchError."""
    from tests_full.metrics.accuracy_report import _assert_schema

    with pytest.raises(SchemaMismatchError, match="never invoked"):
        _assert_schema([], kind="issues", fixture="x", detector_invoked=False)


@pytest.mark.performance
@pytest.mark.p2
@pytest.mark.pipeline
def test_performance_real_pipelines(benchmark, perf_recorder):
    """
    Executes the REAL benchmark suite once (measure_call rounds inside),
    plus a pytest-benchmark timing of batcher for the HTML/CLI benchmark table.
    """
    from pipeline.batcher import create_batches
    from tests_full.metrics.performance_report import _make_doc

    doc = _make_doc(16, 2)
    # pytest-benchmark timed region — REAL create_batches
    benchmark(lambda: create_batches(doc, batch_size=4, overlap=1))

    rows = run_all_benchmarks(rounds=4)
    for r in rows:
        # Drop non-JSON bits
        payload = {k: v for k, v in r.items() if k != "_last_result"}
        warn = warn_if_regression(payload["test"], float(payload["mean_s"]))
        if warn:
            print(warn)
        # Suspiciously fast e2e → fail the harness (not xfail)
        if payload.get("test") == "e2e_parse_batch_aggregate_reformat":
            assert payload["mean_s"] >= 0.05, (
                f"e2e mean {payload['mean_s']}s < 50ms — likely not exercising real DOCX I/O"
            )
        stored = append_result(payload)
        perf_recorder(stored)
        assert payload.get("is_real_pipeline") is True
        assert payload.get("real_path"), "missing real_path documentation"
