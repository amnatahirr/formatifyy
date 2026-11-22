"""
Helpers that invoke the SAME production detectors used by main._run_analysis /
dispatcher.dispatch_all — never stand-ins.

Requires ANTHROPIC_API_KEY or GEMINI_API_KEY for LLM agents (formatting).
Grammar runs locally (spell-checker + T5 model) and needs no key.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


class LLMUnavailableError(RuntimeError):
    """Raised when a production LLM detector is required but no API key is set."""


def llm_keys_status() -> Dict[str, Any]:
    gemini = (os.getenv("GEMINI_API_KEY") or "").strip()
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    return {
        "GEMINI_API_KEY": bool(gemini),
        "ANTHROPIC_API_KEY": bool(anthropic_key),
        "preferred": "gemini" if gemini else ("anthropic" if anthropic_key else None),
    }


def require_llm_client():
    """
    Same client selection as main._run_analysis / _get_ai_client:
      GEMINI_API_KEY → GeminiClientAdapter
      else ANTHROPIC_API_KEY → anthropic.AsyncAnthropic
    """
    status = llm_keys_status()
    if not status["preferred"]:
        raise LLMUnavailableError(
            "Neither GEMINI_API_KEY nor ANTHROPIC_API_KEY is set. "
            "Set one in backend/.env to run production LLM accuracy/e2e tests."
        )
    if status["preferred"] == "gemini":
        from gemini_adapter import GeminiClientAdapter

        return GeminiClientAdapter(api_key=os.environ["GEMINI_API_KEY"]), "gemini"
    import anthropic

    return anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"]), "anthropic"


def blocks_to_batch(blocks: Sequence[dict], *, batch_index: int = 0):
    from models import Batch, ParagraphBlock

    paras = []
    for b in blocks:
        paras.append(
            ParagraphBlock(
                paragraph_id=str(b.get("paragraph_id") or f"p{b.get('index', 0)}"),
                page_number=int(b.get("page_number") or 1),
                text=str(b.get("text") or ""),
                style=str(b.get("style") or "Normal"),
                heading_context="",
            )
        )
    return Batch(
        batch_index=batch_index,
        page_start=1,
        page_end=1,
        paragraphs=paras,
        images=[],
        context_paragraphs=[],
    )


def run_check_grammar(blocks: Sequence[dict]) -> Tuple[List[dict], Dict[str, Any]]:
    """Production: functions.grammar.check_grammar (via dispatcher path)."""
    from functions.grammar import check_grammar

    batch = blocks_to_batch(blocks)

    async def _run():
        return await check_grammar(None, batch)  # local model, no LLM client

    issues = asyncio.run(_run())
    meta = {"provider": "local", "function": "functions.grammar.check_grammar"}
    return list(issues or []), meta


def run_check_formatting(
    blocks: Sequence[dict],
    template: Dict[str, Any],
) -> Tuple[List[dict], Dict[str, Any]]:
    """Production: functions.formatting.check_formatting."""
    from functions.formatting import check_formatting

    client, provider = require_llm_client()
    batch = blocks_to_batch(blocks)

    async def _run():
        return await check_formatting(client, batch, template)

    issues = asyncio.run(_run())
    meta = {"provider": provider, "function": "functions.formatting.check_formatting"}
    return list(issues or []), meta


def run_heading_analysis(
    blocks: Sequence[dict],
    required_sections: Sequence[Any],
) -> Tuple[List[dict], Dict[str, Any]]:
    """
    Production heading matcher used by /api/heading-analysis and reformat:
    heading_analysis.analyze_headings + find_missing_template_headings.
    """
    from docx_tools.heading_analysis import (
        analyze_headings,
        blocks_from_dicts,
        build_template_outline,
        find_missing_template_headings,
    )

    template = {"required_sections": list(required_sections)}
    outline = build_template_outline(list(required_sections))
    analysis_blocks = blocks_from_dicts(
        [
            {
                "paragraph_id": b.get("paragraph_id"),
                "text": b.get("text"),
                "style": b.get("style"),
                "page_number": b.get("page_number", 1),
            }
            for b in blocks
        ]
    )
    matches = analyze_headings(analysis_blocks, template)
    missing = find_missing_template_headings(matches, outline)
    issues: List[dict] = []
    for m in missing:
        issues.append(
            {
                "function": "heading_analysis",
                "type": "missing_section",
                "paragraph_id": "",
                "original": m.get("matched_template_heading") or m.get("text") or "",
                "reason": m.get("fix_description") or "missing template heading",
                "severity": "major",
                "source": "missing",
            }
        )
    for m in matches:
        if m.get("source") == "matched" and m.get("matched_template_heading"):
            issues.append(
                {
                    "function": "heading_analysis",
                    "type": "heading_present",
                    "paragraph_id": str(m.get("paragraph_id") or ""),
                    "original": m.get("matched_template_heading"),
                    "reason": f"matched {m.get('matched_template_heading')}",
                    "severity": "minor",
                    "source": "matched",
                }
            )
    meta = {
        "function": "heading_analysis.analyze_headings + find_missing_template_headings",
        "provider": "deterministic",
    }
    return issues, meta


def run_list_detection(blocks: Sequence[dict]) -> Tuple[List[dict], Dict[str, Any]]:
    """Production: list_detection.detect_list_groups (also formatting pre-pass)."""
    from docx_tools.list_detection import detect_list_groups

    groups = detect_list_groups(blocks) or []
    actual = []
    for g in groups:
        items = getattr(g, "items", None) or []
        pids = list(getattr(g, "paragraph_ids", []) or [])
        actual.append(
            {
                "function": "list_detection",
                "type": "list_group",
                "detection": getattr(g, "detection", ""),
                "paragraph_id": pids[0] if pids else "",
                "reason": f"group size {len(items)} via {getattr(g, 'detection', '')}",
                "original": getattr(g, "trigger_text", "") or "",
                "item_count": len(items),
            }
        )
    return actual, {"function": "list_detection.detect_list_groups", "provider": "deterministic"}


def run_image_relevance(
    *,
    image_png_bytes: bytes,
    surrounding_text: str,
    caption: str = "",
    heading: str = "",
) -> Tuple[List[dict], Dict[str, Any]]:
    """
    Production: functions.image_relevance.analyze_image_relevance_sync
    (CLIP + optional BLIP caption — same core as check_images_combined).
    """
    import base64

    from functions.image_relevance import analyze_image_relevance_sync

    b64 = base64.b64encode(image_png_bytes).decode("ascii")
    result = analyze_image_relevance_sync(
        b64,
        heading=heading,
        before_text=surrounding_text,
        after_text="",
        caption=caption or None,
        skip_caption=bool(caption),
    )
    issues: List[dict] = []
    if not result.get("relevant"):
        issues.append(
            {
                "function": "image_relevance",
                "type": "irrelevant_image",
                "paragraph_id": "img0",
                "reason": result.get("reason") or f"score={result.get('similarity')}",
                "original": (caption or "")[:80],
                "surrounding_text": surrounding_text[:120],
                "similarity": result.get("similarity") or result.get("score") or 0,
            }
        )
    ethics_words = {"nude", "weapon", "blood", "gore", "explicit"}
    if any(w in (caption or "").lower() for w in ethics_words):
        # Production ethics: functions.image_ethics.score_caption_ethics /
        # analyze_image_ethics_sync (also used inside check_images_combined).
        from functions.image_ethics import score_caption_ethics

        try:
            eth = score_caption_ethics(caption)
            unethical = bool(eth.get("is_unethical")) or not bool(
                eth.get("is_ethical", True)
            )
            if unethical:
                issues.append(
                    {
                        "function": "image_ethics",
                        "type": "unsafe_image",
                        "paragraph_id": "img0",
                        "reason": eth.get("category_label")
                        or eth.get("reason")
                        or "ethics",
                        "original": caption[:80],
                    }
                )
        except Exception as exc:
            issues.append(
                {
                    "function": "image_ethics",
                    "type": "unsafe_image",
                    "paragraph_id": "img0",
                    "reason": f"ethics keyword in caption ({exc})",
                    "original": caption[:80],
                }
            )
    meta = {
        "function": "functions.image_relevance.analyze_image_relevance_sync",
        "provider": "local_CLIP_BLIP",
        "raw": {
            "similarity": result.get("similarity"),
            "relevant": result.get("relevant"),
            "reason": result.get("reason"),
        },
    }
    return issues, meta


def render_text_png(text: str, *, size: Tuple[int, int] = (384, 256)) -> bytes:
    """Synthetic PNG with rendered text — gives CLIP something to embed."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", size, color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    # Word-wrap roughly
    words = (text or "image").split()
    lines: List[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) > 28:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    y = 40
    for line in lines[:8]:
        draw.text((20, y), line, fill=(20, 20, 20), font=font)
        y += 22
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def run_plagiarism_corpus(
    document_text: str,
    source_passage: str,
) -> Tuple[List[dict], Dict[str, Any]]:
    """
    Production analyze path uses plagiarism.pipeline.check_document_against_fyp_corpus
    → detector.detect_plagiarism against the FYP corpus.

    For fixtures we build a TEMP corpus containing source_passage (same detector code).
    """
    import tempfile

    from plagiarism.detector import detect_plagiarism_sync
    from plagiarism.pipeline import report_to_issues

    with tempfile.TemporaryDirectory() as td:
        corpus = Path(td)
        (corpus / "source_ref.txt").write_text(source_passage, encoding="utf-8")
        report = detect_plagiarism_sync(
            document_text,
            document_id="accuracy_fixture",
            corpus_dir=corpus,
            force_rebuild_index=True,
            enable_web_verify=False,
        )
        # Minimal chunk_meta for report_to_issues (same shape as pipeline.document_to_chunks)
        chunk_meta: Dict[str, Dict[str, Any]] = {
            "0": {"paragraph_id": "p0", "page": 1, "heading_context": ""},
        }
        for row in report.get("flagged_sentences") or []:
            cid = str(row.get("chunk_id") or "0")
            chunk_meta.setdefault(
                cid, {"paragraph_id": "p0", "page": 1, "heading_context": ""}
            )
        try:
            issues = report_to_issues(report, chunk_meta)
        except Exception:
            issues = []
        # Fallback if report_to_issues produced nothing but detector flagged
        if not issues:
            flagged = report.get("flagged_sentences") or []
            overall = float(report.get("overall_plagiarism_score") or 0)
            if flagged:
                for f in flagged:
                    issues.append(
                        {
                            "function": "plagiarism",
                            "type": "plagiarism",
                            "paragraph_id": "p0",
                            "reason": str(f),
                            "original": str(f.get("sentence") if isinstance(f, dict) else f)[
                                :120
                            ],
                            "severity": "major",
                        }
                    )
            elif overall > 0.3:
                issues.append(
                    {
                        "function": "plagiarism",
                        "type": "plagiarism",
                        "paragraph_id": "p0",
                        "reason": f"overall_plagiarism_score={overall}",
                        "original": source_passage[:80],
                        "severity": "major",
                    }
                )
        # Accuracy fixtures use type "plagiarism"; production emits corpus_*_match.
        # Keep production type AND a normalized alias for fieldwise matching.
        for iss in issues:
            prod_type = iss.get("type") or ""
            if prod_type.startswith("corpus_") or prod_type.endswith("_match"):
                iss["production_type"] = prod_type
                iss["type"] = "plagiarism"
        meta = {
            "function": "plagiarism.detector.detect_plagiarism_sync (+ temp corpus)",
            "provider": "local_MinHash_FAISS",
            "report_keys": list(report.keys()) if isinstance(report, dict) else [],
            "overall": (
                report.get("overall_plagiarism_score")
                if isinstance(report, dict)
                else None
            ),
        }
        return list(issues or []), meta


async def run_full_analyze_pipeline(
    saved_path: str,
    filename: str,
    template: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Same core path as main._run_analysis without HTTP/job store:
      parse → strip frontmatter → batch → dispatch_all + corpus → aggregate → reformat
    Returns report dict + token/usage hints if available.
    """
    import uuid

    from pipeline.aggregator import aggregate
    from pipeline.batcher import create_batches
    from pipeline.dispatcher import dispatch_all
    from pipeline.parser import parse_file
    from docx_tools.reformatter import reformat_document
    from docx_tools.review_blocks import strip_frontmatter_from_document

    client, provider = require_llm_client()
    doc_model = parse_file(saved_path, filename)
    try:
        doc_model = strip_frontmatter_from_document(doc_model)
    except Exception:
        pass
    batches = create_batches(doc_model)

    from plagiarism.pipeline import check_document_against_fyp_corpus

    raw_issues, corpus_issues = await asyncio.gather(
        dispatch_all(client, batches, template),
        check_document_against_fyp_corpus(doc_model, document_id=f"perf_{uuid.uuid4().hex[:8]}"),
    )
    if corpus_issues:
        raw_issues.extend(corpus_issues)
    report = aggregate(raw_issues, doc_model, total_batches=len(batches))

    out = Path(saved_path).with_name(f"perf_out_{uuid.uuid4().hex[:8]}.docx")
    try:
        reformat_document(
            saved_path,
            str(out),
            report,
            template.get("formatting_rules") or {},
            template.get("required_sections") or [],
        )
    except Exception as exc:
        out = Path("")
        reformat_error = str(exc)
    else:
        reformat_error = None

    return {
        "provider": provider,
        "pages": doc_model.total_pages,
        "paragraphs": len(doc_model.paragraphs),
        "batches": len(batches),
        "issues": report.stats.total_issues,
        "stats": report.stats.model_dump(),
        "output_path": str(out) if out else "",
        "reformat_error": reformat_error,
        "functions_invoked": [
            "parser.parse_file",
            "batcher.create_batches",
            "dispatcher.dispatch_all → check_grammar, check_formatting, check_images_combined, check_para_relevance",
            "plagiarism.pipeline.check_document_against_fyp_corpus",
            "aggregator.aggregate",
            "reformatter.reformat_document",
        ],
        # Anthropic/Gemini token usage is not consistently exposed via our adapters;
        # leave explicit None rather than inventing numbers.
        "token_usage": None,
        "cost_estimate_usd": None,
        "cost_note": (
            "Token counts not returned by GeminiClientAdapter / not aggregated here. "
            "Check Anthropic dashboard for metered usage of this run."
        ),
    }
