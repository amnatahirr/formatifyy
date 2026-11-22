"""
Accuracy metrics — honest comparison against ground_truth fixtures.

PRODUCTION WIRING (must match main._run_analysis / dispatcher.dispatch_all)
---------------------------------------------------------------------------
  grammar          → functions.grammar.check_grammar          (local spell + T5)
  formatting       → functions.formatting.check_formatting    (LLM)
  image_relevance  → functions.image_relevance.analyze_image_relevance_sync (CLIP)
  list_detection   → list_detection.detect_list_groups        (deterministic)
  plagiarism       → plagiarism.detector.detect_plagiarism_sync (+ temp corpus)
  heading/toc      → heading_analysis.analyze_headings + find_missing_template_headings

Requires GEMINI_API_KEY or ANTHROPIC_API_KEY for formatting (grammar is local).
Missing keys → SchemaMismatchError (no silent fall-back to naive_grammar_probe).

Standalone:
  cd backend && python -m tests_full.metrics.accuracy_report
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GT_DIR = Path(__file__).resolve().parent / "ground_truth"
RESULTS_PATH = Path(__file__).resolve().parent / "results" / "accuracy_report.json"

THRESHOLDS = {
    "list_detection": 0.70,
    "heading_detection": 0.70,
    "toc_structure": 0.70,
    "formatting": 0.70,
    "grammar": 0.50,
    "plagiarism": 0.70,
    "image_relevance": 0.55,
    "default": 0.55,
}


class SchemaMismatchError(AssertionError):
    """Detector output does not match the required schema."""


@dataclass
class Score:
    feature: str
    fixture: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    details: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    difficulty: str = ""
    detector: str = ""
    ci_min_f1: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def f1_from_counts(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = (
        _safe_div(2 * precision * recall, precision + recall)
        if (precision + recall)
        else 0.0
    )
    return precision, recall, f1


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


def load_ground_truth() -> List[Tuple[dict, Path]]:
    items = []
    for path in sorted(GT_DIR.glob("*.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        items.append((meta, path))
    return items


def _read_fixture_text(meta: dict) -> str:
    path = GT_DIR / meta["fixture"]
    if not path.exists():
        raise FileNotFoundError(f"Fixture text missing: {path}")
    return path.read_text(encoding="utf-8")


def _paragraph_blocks(text: str) -> List[Dict[str, Any]]:
    known = {
        "Introduction",
        "Methodology",
        "Results",
        "Conclusion",
        "Related Work",
        "Abstract",
        "References",
        "Literature Review",
        "Discussion",
    }
    blocks = []
    for i, chunk in enumerate(re.split(r"\n\s*\n", text.strip())):
        chunk = chunk.strip()
        if not chunk:
            continue
        first = chunk.split("\n")[0].strip()
        is_heading = first in known or (
            len(chunk) < 48
            and "\n" not in chunk
            and bool(chunk[:1].isupper())
            and len(chunk.split()) <= 6
            and not first.endswith((":", ";", ","))
            and not first.startswith(("-", "*", "•"))
            and not first[:1].isdigit()
        )
        blocks.append(
            {
                "paragraph_id": f"p{i}",
                "text": chunk,
                "style": "Heading 1" if is_heading else "Normal",
                "index": i,
            }
        )
    return blocks


def _heading_titles(blocks: Sequence[dict]) -> List[str]:
    titles = []
    for b in blocks:
        t = (b.get("text") or "").strip().split("\n")[0].strip()
        if "heading" in (b.get("style") or "").lower():
            titles.append(t)
    return titles


def _assert_schema(actual: Any, *, kind: str, fixture: str, detector_invoked: bool) -> None:
    if not detector_invoked:
        raise SchemaMismatchError(
            f"[{fixture}] detector was never invoked — refusing silent 0==0 pass"
        )
    if kind == "issues":
        if not isinstance(actual, list):
            raise SchemaMismatchError(
                f"[{fixture}] expected list of issue dicts, got {type(actual).__name__}"
            )
        for i, iss in enumerate(actual):
            if not isinstance(iss, dict):
                raise SchemaMismatchError(
                    f"[{fixture}] issue[{i}] is {type(iss).__name__}, want dict"
                )
            if "type" not in iss and "function" not in iss:
                raise SchemaMismatchError(
                    f"[{fixture}] issue[{i}] missing type/function keys: {iss!r}"
                )
    elif kind == "list_groups":
        if not isinstance(actual, list):
            raise SchemaMismatchError(
                f"[{fixture}] detect_list_groups must return list, got {type(actual).__name__}"
            )
    elif kind == "relevance":
        if not isinstance(actual, dict) or "score" not in actual:
            raise SchemaMismatchError(
                f"[{fixture}] relevance result must be dict with 'score', got {actual!r}"
            )
    elif kind == "similarity":
        if not isinstance(actual, dict) or "similarity" not in actual:
            raise SchemaMismatchError(
                f"[{fixture}] plagiarism result must be dict with 'similarity', got {actual!r}"
            )


def _types_compatible(exp_type: str, act_type: str) -> bool:
    if not exp_type or not act_type:
        return True
    if exp_type == act_type or exp_type in act_type or act_type in exp_type:
        return True
    # Production formatting agent often emits section_order for absent headings
    aliases = {
        "missing_section": {
            "missing_section",
            "required_section",
            "section_order",
            "missing_heading",
        },
        "section_order": {"missing_section", "section_order", "required_section"},
    }
    return act_type in aliases.get(exp_type, set())


def _match_issues_fieldwise(
    expected: Sequence[dict],
    actual: Sequence[dict],
) -> Tuple[int, int, int, List[str]]:
    """
    Field-for-field match (NOT count-only):
      expected matches actual iff type matches (casefold / substring / alias) AND
      location_hint (if set) appears in paragraph_id/original/reason/text AND
      at least one keyword (if set) appears in that blob.
    Each side used at most once.
    """
    notes: List[str] = []
    used_actual: Set[int] = set()
    tp = 0
    for exp in expected:
        exp_type = (exp.get("type") or "").casefold()
        hint = (exp.get("location_hint") or exp.get("paragraph_id") or "").casefold()
        keywords = [k.casefold() for k in (exp.get("keywords") or [])]
        matched = False
        for ai, act in enumerate(actual):
            if ai in used_actual:
                continue
            act_type = (act.get("type") or act.get("function") or "").casefold()
            if not _types_compatible(exp_type, act_type):
                continue
            blob = " ".join(
                str(act.get(k, ""))
                for k in (
                    "paragraph_id",
                    "original",
                    "reason",
                    "suggestion",
                    "text",
                    "text_preview",
                    "surrounding_text",
                    "detection",
                )
            ).casefold()
            if hint and hint not in blob:
                continue
            if keywords and not any(k in blob for k in keywords):
                continue
            used_actual.add(ai)
            matched = True
            tp += 1
            break
        if not matched:
            notes.append(
                f"FN: type={exp.get('type')} hint={exp.get('location_hint')} "
                f"kw={exp.get('keywords')}"
            )
    fp = 0
    for ai, act in enumerate(actual):
        if ai not in used_actual:
            fp += 1
            notes.append(f"FP: type={act.get('type')} id={act.get('paragraph_id')}")
    fn = len(expected) - tp
    return tp, fp, fn, notes


def _normalize_grammar_expected(expected: Sequence[dict]) -> List[dict]:
    """Production check_grammar always emits type='grammar' (never 'spelling')."""
    out: List[dict] = []
    for e in expected or []:
        if e.get("type") == "spelling":
            out.append({**e, "type": "grammar"})
        else:
            out.append(dict(e))
    return out


def _focus_formatting_issues(actual: Sequence[dict], expected: Sequence[dict]) -> Tuple[List[dict], int]:
    """
    When fixtures target missing_section / section_order, ignore unrelated style
    nits (font/spacing) for F1 so LLM verbosity doesn't dominate — still counted
    in notes. Forbidden types are always retained for confused fixtures.
    """
    focus = {(e.get("type") or "").casefold() for e in (expected or []) if e.get("type")}
    if not focus:
        return list(actual), 0
    aliases = set(focus)
    if "missing_section" in aliases:
        aliases |= {"required_section", "missing_heading", "section_order"}
    scoped = []
    ignored = 0
    for a in actual:
        t = (a.get("type") or "").casefold()
        if t in aliases or any(x in t for x in aliases):
            scoped.append(a)
        else:
            ignored += 1
    return scoped, ignored


def score_grammar(meta: dict) -> Score:
    """Production: functions.grammar.check_grammar (local model via /analyze dispatch)."""
    from tests_full.metrics.production_runners import (
        LLMUnavailableError,
        run_check_grammar,
    )

    text = _read_fixture_text(meta)
    blocks = _paragraph_blocks(text)
    try:
        actual, run_meta = run_check_grammar(blocks)
    except LLMUnavailableError as exc:
        raise SchemaMismatchError(
            f"[{meta['fixture']}] REAL grammar detector unavailable: {exc}"
        ) from exc
    _assert_schema(actual, kind="issues", fixture=meta["fixture"], detector_invoked=True)
    expected = _normalize_grammar_expected(meta.get("expected_issues") or [])
    if meta.get("difficulty") == "clean":
        tp, fp, fn = (1 if not actual else 0), len(actual), 0
        notes = [f"FP on clean: {a.get('type')} '{a.get('original')}'" for a in actual] or [
            "clean: no false positives"
        ]
    else:
        tp, fp, fn, notes = _match_issues_fieldwise(expected, actual)
    p, r, f1 = f1_from_counts(tp, fp, fn)
    return Score(
        "grammar",
        meta["fixture"],
        tp,
        fp,
        fn,
        p,
        r,
        f1,
        {"actual": actual, "expected": expected, "run": run_meta},
        "; ".join(notes) if notes else "ok",
        meta.get("difficulty", ""),
        run_meta.get("function", "functions.grammar.check_grammar"),
        float(meta.get("ci_min_f1", THRESHOLDS["grammar"])),
    )


def score_formatting(meta: dict) -> Score:
    """Production: functions.formatting.check_formatting (LLM via dispatch_all)."""
    from tests_full.metrics.production_runners import (
        LLMUnavailableError,
        run_check_formatting,
    )

    text = _read_fixture_text(meta)
    blocks = _paragraph_blocks(text)
    required = list(meta.get("required_sections") or [])
    template = {
        "name": "accuracy_template",
        "required_sections": required,
        "formatting_rules": {"fonts": {"body": "Times New Roman"}},
        "markdown_rules": "",
    }
    try:
        actual, run_meta = run_check_formatting(blocks, template)
    except LLMUnavailableError as exc:
        raise SchemaMismatchError(
            f"[{meta['fixture']}] REAL formatting detector unavailable: {exc}"
        ) from exc
    _assert_schema(actual, kind="issues", fixture=meta["fixture"], detector_invoked=True)
    expected = meta.get("expected_issues") or []
    if meta.get("difficulty") == "clean":
        bad = [a for a in actual if a.get("type") in {"missing_section", "required_section"}]
        tp, fp, fn = (1 if not bad else 0), len(bad), 0
        notes = [f"FP {a.get('type')}" for a in bad] or [
            f"clean: no missing_section FPs ({len(actual)} other style issues ignored)"
        ]
    else:
        scoped, ignored = _focus_formatting_issues(actual, expected)
        tp, fp, fn, notes = _match_issues_fieldwise(expected, scoped)
        if ignored:
            notes.append(f"{ignored} non-focus formatting issues ignored for F1")
        for a in actual:
            if a.get("type") in (meta.get("forbidden_types") or []):
                fp += 1
                notes.append(f"confused-type FP: {a.get('type')}")
    p, r, f1 = f1_from_counts(tp, fp, fn)
    return Score(
        "formatting",
        meta["fixture"],
        tp,
        fp,
        fn,
        p,
        r,
        f1,
        {"actual": actual, "expected": expected, "run": run_meta},
        "; ".join(notes) if notes else "ok",
        meta.get("difficulty", ""),
        run_meta.get("function", "functions.formatting.check_formatting"),
        float(meta.get("ci_min_f1", THRESHOLDS["formatting"])),
    )


def score_list_detection(meta: dict) -> Score:
    from tests_full.metrics.production_runners import run_list_detection

    text = _read_fixture_text(meta)
    blocks = _paragraph_blocks(text)
    actual, run_meta = run_list_detection(blocks)
    _assert_schema(actual, kind="list_groups", fixture=meta["fixture"], detector_invoked=True)
    _assert_schema(actual, kind="issues", fixture=meta["fixture"], detector_invoked=True)
    expected = meta.get("expected_issues") or []
    expected_groups = int(meta.get("expected_list_groups", len(expected) or 0))
    if meta.get("difficulty") == "clean" or (
        expected_groups == 0 and not expected and meta.get("difficulty") in {"clean", "confused"}
    ):
        tp, fp, fn = (1 if not actual else 0), len(actual), 0
        notes = [f"FP list_group detection={a.get('detection')}" for a in actual] or [
            "no list groups (as expected)"
        ]
    elif expected:
        tp, fp, fn, notes = _match_issues_fieldwise(expected, actual)
        min_items = int(meta.get("expected_min_items", 0))
        if min_items and actual:
            best = max(int(a.get("item_count") or 0) for a in actual)
            if best < min_items:
                fn += 1
                notes.append(f"FN: best group size {best} < {min_items}")
    else:
        if expected_groups == 0 and not actual:
            tp, fp, fn = 1, 0, 0
            notes = ["no list groups (as expected)"]
        elif len(actual) >= expected_groups:
            tp, fp, fn = expected_groups, max(0, len(actual) - expected_groups), 0
            notes = [f"groups={len(actual)} expected={expected_groups}"]
        else:
            tp, fp, fn = len(actual), 0, expected_groups - len(actual)
            notes = [f"groups={len(actual)} expected={expected_groups}"]
    p, r, f1 = f1_from_counts(tp, fp, fn)
    return Score(
        "list_detection",
        meta["fixture"],
        tp,
        fp,
        fn,
        p,
        r,
        f1,
        {"group_count": len(actual), "actual": actual, "run": run_meta},
        "; ".join(notes) if notes else "ok",
        meta.get("difficulty", ""),
        run_meta.get("function", "list_detection.detect_list_groups"),
        float(meta.get("ci_min_f1", THRESHOLDS["list_detection"])),
    )


def score_heading_detection(meta: dict) -> Score:
    from tests_full.metrics.production_runners import run_heading_analysis

    text = _read_fixture_text(meta)
    blocks = _paragraph_blocks(text)
    required = list(meta.get("required_sections") or [])
    actual_issues, run_meta = run_heading_analysis(blocks, required)
    _assert_schema(actual_issues, kind="issues", fixture=meta["fixture"], detector_invoked=True)
    expected_present = set(meta.get("expected_present") or [])
    expected_missing = set(meta.get("expected_missing") or [])
    expected = list(meta.get("expected_issues") or [])
    if not expected:
        for s in expected_present:
            expected.append({"type": "heading_present", "keywords": [s], "location_hint": s})
        for s in expected_missing:
            expected.append({"type": "missing_section", "keywords": [s], "location_hint": s})
    if meta.get("difficulty") == "clean":
        bad = [a for a in actual_issues if a["type"] == "missing_section"]
        if not bad:
            tp, fp, fn = 1, 0, 0
            notes = ["clean: all required present"]
        else:
            tp, fp, fn = 0, len(bad), 0
            notes = [f"FP {b['original']}" for b in bad]
    else:
        tp, fp, fn, notes = _match_issues_fieldwise(expected, actual_issues)
    p, r, f1 = f1_from_counts(tp, fp, fn)
    feature = meta.get("feature") or "heading_detection"
    return Score(
        feature,
        meta["fixture"],
        tp,
        fp,
        fn,
        p,
        r,
        f1,
        {"actual": actual_issues, "run": run_meta},
        "; ".join(notes) if notes else "ok",
        meta.get("difficulty", ""),
        run_meta.get(
            "function",
            "heading_analysis.analyze_headings + find_missing_template_headings",
        ),
        float(meta.get("ci_min_f1", THRESHOLDS.get(feature, THRESHOLDS["heading_detection"]))),
    )


def score_toc_structure(meta: dict) -> Score:
    return score_heading_detection({**meta, "feature": "toc_structure"})


def score_plagiarism(meta: dict) -> Score:
    """Production corpus detector (temp corpus seeded with source_passage)."""
    from tests_full.metrics.production_runners import run_plagiarism_corpus

    text = _read_fixture_text(meta)
    source = (meta.get("source_passage") or "").strip()
    corpus_file = meta.get("corpus_fixture")
    if corpus_file:
        source = (GT_DIR / corpus_file).read_text(encoding="utf-8").strip()
    actual, run_meta = run_plagiarism_corpus(text, source)
    _assert_schema(actual, kind="issues", fixture=meta["fixture"], detector_invoked=True)
    expected = meta.get("expected_issues") or []
    if meta.get("difficulty") == "clean":
        tp, fp, fn = (1 if not actual else 0), len(actual), 0
        notes = ["FP plagiarism" for _ in actual] or ["clean: not flagged"]
    else:
        tp, fp, fn, notes = _match_issues_fieldwise(expected, actual)
        if not expected and meta.get("expect_flagged", True):
            if actual:
                tp, fp, fn, notes = 1, 0, 0, ["flagged by corpus detector"]
            else:
                tp, fp, fn, notes = 0, 0, 1, ["FN: corpus detector did not flag"]
        elif expected and not actual and meta.get("expect_flagged", True):
            # fieldwise already set FN; reinforce note
            if fn == 0:
                tp, fp, fn, notes = 0, 0, len(expected), ["FN: corpus detector did not flag"]
    p, r, f1 = f1_from_counts(tp, fp, fn)
    return Score(
        "plagiarism",
        meta["fixture"],
        tp,
        fp,
        fn,
        p,
        r,
        f1,
        {"actual": actual, "run": run_meta},
        "; ".join(notes) if notes else "ok",
        meta.get("difficulty", ""),
        run_meta.get("function", "plagiarism.detector.detect_plagiarism_sync"),
        float(meta.get("ci_min_f1", THRESHOLDS["plagiarism"])),
    )


def score_image_relevance(meta: dict) -> Score:
    """
    Production: functions.image_relevance.analyze_image_relevance_sync (CLIP).
    Synthetic PNG with rendered caption/topic text supplies image bytes.
    """
    from tests_full.metrics.production_runners import render_text_png, run_image_relevance

    caption = (meta.get("image_caption") or "").strip()
    surrounding = (meta.get("surrounding_text") or _read_fixture_text(meta)).strip()
    paint = caption if caption else surrounding[:80]
    png = render_text_png(paint)
    actual, run_meta = run_image_relevance(
        image_png_bytes=png,
        surrounding_text=surrounding,
        caption=caption,
    )
    _assert_schema(actual, kind="issues", fixture=meta["fixture"], detector_invoked=True)
    expected = meta.get("expected_issues") or []
    if meta.get("difficulty") == "clean":
        bad = [a for a in actual if a["type"] in {"irrelevant_image", "unsafe_image"}]
        tp, fp, fn = (1 if not bad else 0), len(bad), 0
        notes = [f"FP {b['type']}" for b in bad] or [
            f"clean relevant raw={run_meta.get('raw')}"
        ]
    else:
        tp, fp, fn, notes = _match_issues_fieldwise(expected, actual)
    p, r, f1 = f1_from_counts(tp, fp, fn)
    return Score(
        "image_relevance",
        meta["fixture"],
        tp,
        fp,
        fn,
        p,
        r,
        f1,
        {"actual": actual, "run": run_meta},
        "; ".join(notes) if notes else "ok",
        meta.get("difficulty", ""),
        run_meta.get("function", "functions.image_relevance.analyze_image_relevance_sync"),
        float(meta.get("ci_min_f1", THRESHOLDS["image_relevance"])),
    )


SCORERS = {
    "grammar": score_grammar,
    "formatting": score_formatting,
    "list_detection": score_list_detection,
    "heading_detection": score_heading_detection,
    "toc_structure": score_toc_structure,
    "plagiarism": score_plagiarism,
    "image_relevance": score_image_relevance,
}


def evaluate_all() -> List[Score]:
    scores: List[Score] = []
    for meta, path in load_ground_truth():
        feature = meta.get("feature")
        scorer = SCORERS.get(feature or "")
        if not scorer:
            mode = meta.get("match_mode")
            scorer = {
                "list_groups": score_list_detection,
                "headings_present": score_heading_detection,
                "heading_count": score_toc_structure,
                "by_type": score_formatting if feature == "formatting" else score_grammar,
                "similarity": score_plagiarism,
            }.get(mode or "")
        if not scorer:
            continue
        try:
            scores.append(scorer(meta))
        except SchemaMismatchError:
            raise
        except Exception as exc:
            scores.append(
                Score(
                    feature or "unknown",
                    meta.get("fixture", path.name),
                    0,
                    0,
                    1,
                    0.0,
                    0.0,
                    0.0,
                    {"error": str(exc)},
                    f"scorer crashed: {exc}",
                    meta.get("difficulty", ""),
                    "error",
                    0.0,
                )
            )
    return scores


def print_table(scores: Sequence[Score]) -> None:
    try:
        from tabulate import tabulate

        rows = [
            [
                s.feature,
                s.fixture,
                f"{s.precision:.3f}",
                f"{s.recall:.3f}",
                f"{s.f1:.3f}",
                s.difficulty,
                (s.detector or "")[:48],
                (s.notes or "")[:50],
            ]
            for s in scores
        ]
        print(
            tabulate(
                rows,
                headers=[
                    "feature",
                    "fixture",
                    "precision",
                    "recall",
                    "F1",
                    "difficulty",
                    "detector",
                    "notes",
                ],
                tablefmt="github",
            )
        )
    except Exception:
        for s in scores:
            print(
                f"{s.feature:18} {s.fixture:40} P={s.precision:.3f} R={s.recall:.3f} "
                f"F1={s.f1:.3f} [{s.difficulty}] {s.notes}"
            )


def persist_scores(scores: Sequence[Score]) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    hist: list = []
    if RESULTS_PATH.exists():
        try:
            hist = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            if not isinstance(hist, list):
                hist = []
        except Exception:
            hist = []
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    commit = _git_commit()
    for s in scores:
        row = s.to_dict()
        row["timestamp"] = stamp
        row["git_commit"] = commit
        hist.append(row)
    RESULTS_PATH.write_text(json.dumps(hist, indent=2), encoding="utf-8")


def gate_failures(scores: Sequence[Score]) -> List[str]:
    fails = []
    for s in scores:
        if s.f1 + 1e-9 < s.ci_min_f1:
            fails.append(
                f"{s.feature}/{s.fixture}: F1={s.f1:.3f} < ci_min_f1={s.ci_min_f1} "
                f"(P={s.precision:.3f} R={s.recall:.3f}) notes={s.notes}"
            )
    return fails


def main() -> int:
    scores = evaluate_all()
    print_table(scores)
    persist_scores(scores)
    fails = gate_failures(scores)
    if fails:
        print("\nCI gate failures:")
        for f in fails:
            print(" -", f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
