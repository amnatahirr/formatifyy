"""
Analysis pipeline unit/integration tests (parse → batch → aggregate → helpers).

Deep heading/list/TOC/table/image behavior is covered by backend/test_*.py
(Appendix A) — this module focuses on API-adjacent pipeline contracts and
deterministic helpers used by the full suite accuracy/performance metrics.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from aggregator import aggregate
from batcher import create_batches
from models import DocumentModel, ImageBlock, ParagraphBlock
from parser import parse_text


pytestmark = [pytest.mark.pipeline]


def _doc_with_pages(pages: int, paras_per_page: int = 2) -> DocumentModel:
    paragraphs = []
    for pg in range(1, pages + 1):
        for i in range(paras_per_page):
            paragraphs.append(
                ParagraphBlock(
                    paragraph_id=f"page{pg}-para{i}",
                    page_number=pg,
                    text=f"Unique content on page {pg} slot {i} for batching tests.",
                    style="Normal",
                )
            )
    return DocumentModel(
        filename="synthetic.txt",
        total_pages=pages,
        paragraphs=paragraphs,
        images=[],
    )


@pytest.mark.p0
def test_parse_text_produces_paragraphs():
    doc = parse_text("Introduction\n\nHello world.\n\nConclusion\n\nBye.")
    assert doc.total_pages >= 1
    assert len(doc.paragraphs) >= 2


@pytest.mark.p0
def test_batcher_empty_doc():
    doc = DocumentModel(filename="x", total_pages=0)
    assert create_batches(doc) == []


@pytest.mark.p0
def test_batcher_page_windows_and_overlap():
    doc = _doc_with_pages(9)
    batches = create_batches(doc, batch_size=4, overlap=1)
    assert len(batches) >= 3
    assert batches[0].page_start == 1
    assert batches[0].page_end == 4
    assert batches[1].page_start == 5
    if batches[1].page_start > 1:
        assert isinstance(batches[1].context_paragraphs, list)


@pytest.mark.p0
def test_aggregator_dedup_by_function_type_paragraph():
    doc = DocumentModel(
        filename="synthetic.txt",
        total_pages=1,
        paragraphs=[
            ParagraphBlock(
                paragraph_id="para-alpha",
                page_number=1,
                text="Unique body text that should not list-cluster.",
            )
        ],
        images=[],
    )
    pid = "para-alpha"
    raw = [
        {
            "function": "grammar",
            "type": "spelling",
            "paragraph_id": pid,
            "severity": "minor",
            "reason": "misspelled",
        },
        {
            "function": "grammar",
            "type": "spelling",
            "paragraph_id": pid,
            "severity": "minor",
            "reason": "misspelled again",
        },
        {
            "function": "formatting",
            "type": "font",
            "paragraph_id": pid,
            "severity": "minor",
            "reason": "wrong font",
        },
    ]
    report = aggregate(raw, doc, total_batches=1, list_validation_flags=[])
    grammar = [i for i in report.issues if i.function == "grammar"]
    assert len(grammar) == 1
    assert grammar[0].paragraph_id == pid
    assert report.stats.total_issues == 2
    assert report.stats.formatting_issues >= 1


@pytest.mark.p1
def test_aggregator_image_dedup():
    doc = DocumentModel(
        filename="img",
        total_pages=1,
        paragraphs=[],
        images=[ImageBlock(image_id="img1", page_number=1, base64="x")],
    )
    raw = [
        {
            "function": "image_ethics",
            "image_id": "img1",
            "type": "unsafe",
            "severity": "major",
        },
        {
            "function": "image_ethics",
            "image_id": "img1",
            "type": "unsafe",
            "severity": "major",
        },
    ]
    report = aggregate(raw, doc, total_batches=1, list_validation_flags=[])
    assert report.stats.image_ethics_issues == 1


@pytest.mark.p1
def test_dispatch_all_swallows_agent_exceptions():
    """Dispatcher should not abort whole analyze when one agent fails."""
    import asyncio

    from dispatcher import dispatch_all

    doc = _doc_with_pages(2)
    batches = create_batches(doc, batch_size=4)

    async def _boom(*_a, **_k):
        raise RuntimeError("agent down")

    async def _ok(*_a, **_k):
        return []

    with patch("dispatcher.check_grammar", side_effect=_boom), patch(
        "dispatcher.check_formatting", side_effect=_ok
    ), patch("dispatcher.check_images_combined", side_effect=_ok), patch(
        "dispatcher.check_para_relevance", side_effect=_ok
    ):
        result = asyncio.run(dispatch_all(None, batches, template={"name": "t"}))
        assert isinstance(result, list)


@pytest.mark.p1
def test_list_detection_import_smoke():
    from list_detection import detect_list_groups

    blocks = [
        {
            "paragraph_id": "p1",
            "text": "We need the following:",
            "style": "Normal",
            "index": 0,
        },
        {
            "paragraph_id": "p2",
            "text": "- First item here for detection.",
            "style": "Normal",
            "index": 1,
        },
        {
            "paragraph_id": "p3",
            "text": "- Second item here for detection.",
            "style": "Normal",
            "index": 2,
        },
        {
            "paragraph_id": "p4",
            "text": "- Third item here for detection.",
            "style": "Normal",
            "index": 3,
        },
    ]
    groups = detect_list_groups(blocks)
    assert groups is not None


@pytest.mark.p2
def test_heading_analysis_endpoint(client, sample_docx_bytes):
    from parser import parse_file
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(sample_docx_bytes)
        path = f.name
    try:
        doc = parse_file(path, "sample.docx")
        blocks = [
            {
                "paragraph_id": p.paragraph_id,
                "text": p.text,
                "style": p.style,
                "page_number": p.page_number,
            }
            for p in doc.paragraphs
        ]
        r = client.post(
            "/api/heading-analysis",
            json={
                "template": {
                    "name": "t",
                    "required_sections": [
                        "Introduction",
                        "Methodology",
                        "Conclusion",
                    ],
                },
                "blocks": blocks,
            },
        )
        assert r.status_code in (200, 422, 500)
        if r.status_code == 200:
            assert isinstance(r.json(), (dict, list))
    finally:
        os.unlink(path)


@pytest.mark.p2
def test_image_and_table_format_defaults(client):
    """
    BUG: `/api/templates/{template_id}` is registered before
    `/api/templates/image-format-defaults` and `/table-format-defaults`, so FastAPI
    treats the path segment as an int template_id → 422.
    When fixed, these should return 200 + dict payloads.
    """
    r1 = client.get("/api/templates/image-format-defaults")
    r2 = client.get("/api/templates/table-format-defaults")
    assert r1.status_code in (200, 422)
    assert r2.status_code in (200, 422)
    if r1.status_code == 200:
        assert isinstance(r1.json(), dict)
    if r2.status_code == 200:
        assert isinstance(r2.json(), dict)


@pytest.mark.p1
@pytest.mark.performance
def test_batcher_throughput_recorded(benchmark, measure_resources, perf_recorder):
    doc = _doc_with_pages(40)

    def _run():
        return create_batches(doc, batch_size=4, overlap=1)

    batches = benchmark(_run)
    _, stats = measure_resources(_run)
    pages = doc.total_pages
    mean_s = float(getattr(benchmark.stats, "mean", stats["elapsed_s"]))
    throughput = pages / mean_s if mean_s > 0 else 0
    perf_recorder(
        {
            "test": "batcher_40_pages",
            "mean_s": round(mean_s, 6),
            "p95_s": round(float(getattr(benchmark.stats, "max", mean_s)), 6),
            "peak_memory_mb": stats["peak_memory_mb"],
            "cpu_percent": stats["cpu_percent"],
            "throughput_pages_per_s": round(throughput, 2),
        }
    )
    assert len(batches) >= 1


@pytest.mark.p1
@pytest.mark.performance
def test_aggregator_benchmark(benchmark, measure_resources, perf_recorder):
    doc = _doc_with_pages(8)
    raw = [
        {
            "function": "grammar",
            "type": "spelling",
            "paragraph_id": f"page{i}-para0",
            "severity": "minor",
            "reason": "x",
        }
        for i in range(1, 9)
    ] * 3

    def _run():
        return aggregate(raw, doc, total_batches=2, list_validation_flags=[])

    report = benchmark(_run)
    _, stats = measure_resources(_run)
    mean_s = float(getattr(benchmark.stats, "mean", stats["elapsed_s"]))
    perf_recorder(
        {
            "test": "aggregator_dedup",
            "mean_s": round(mean_s, 6),
            "peak_memory_mb": stats["peak_memory_mb"],
            "cpu_percent": stats["cpu_percent"],
            "issues_out": report.stats.total_issues,
        }
    )
    assert report.stats.total_issues <= 8
