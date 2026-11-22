"""Progress updates must reach the job dict through the same thread hops the
real analysis uses: worker task -> to_thread -> asyncio.run -> to_thread."""
from __future__ import annotations

import asyncio

import analysis_progress as ap


def test_progress_propagates_through_threads_and_never_goes_back():
    job = {"status": "processing"}

    def grammar_thread():
        ap.grammar_progress(3, 10)
        ap.grammar_progress(1, 10)  # out-of-order report must not lower the bar

    async def pipeline():
        ap.set_stage("reading")
        await asyncio.to_thread(grammar_thread)

    def analysis_in_thread():
        return asyncio.run(pipeline())

    async def worker():
        ap.bind(job)
        await asyncio.to_thread(analysis_in_thread)

    asyncio.run(worker())
    p = job["progress"]
    assert p["stage"] == "grammar"
    assert p["detail"] == "Grammar: sentence 1 of 10"
    assert p["percent"] == int(25 + 65 * 0.3)


def test_no_job_bound_is_a_noop():
    ap.set_stage("reading")
    ap.grammar_progress(1, 2)  # must not raise
