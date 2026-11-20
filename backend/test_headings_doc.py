"""
test_headings_doc.py  -  try heading detection on ONE .docx, local vs Claude.

It parses the file with the app's own parser (pipeline/parser.py), then runs
engine.detect_headings() twice:
    1. ENGINE=local  (XGBoost; asks Claude only below the threshold)
    2. ENGINE=api    (the old Claude-only version)
and prints one line per paragraph:
    text | local label | confidence | used_fallback | api label | same?

Claude is only called if ANTHROPIC_API_KEY is set (backend/.env is read).
Without a key: local runs with no fallback, and the API column is skipped.

Run (inside backend/, venv active, see instructions):
    python test_headings_doc.py "path/to/report.docx"
    python test_headings_doc.py report.docx --show headings   # only lines anyone calls H1/H2/H3/Caption
    python test_headings_doc.py report.docx --show diff       # only lines where local and api disagree
    python test_headings_doc.py report.docx --no-api          # local only, no Claude at all
"""
import argparse
import asyncio
import contextlib
import io
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
from pipeline.parser import parse_file  # noqa: E402


def cut(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


async def run(engine_name, client, blocks):
    engine.ENGINE = engine_name          # same switch as the ENGINE env variable
    return await engine.detect_headings(client, blocks, use_style=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--show", choices=["all", "headings", "diff"], default="all")
    ap.add_argument("--no-api", action="store_true", help="never call Claude")
    ap.add_argument("--width", type=int, default=60, help="text column width")
    args = ap.parse_args()

    path = Path(args.docx)
    if path.suffix.lower() != ".docx":
        sys.exit("Please give a .docx file.")
    with contextlib.redirect_stdout(io.StringIO()):   # hide the parser's debug prints
        doc = parse_file(str(path), path.name)
    blocks = [b for b in doc.paragraphs if (b.text or "").strip()]

    client = None
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key and not args.no_api:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=key)

    from functions.heading_local import MODEL_PATH
    print(f"File: {path.name}  |  {len(blocks)} paragraphs")
    print(f"Model: {MODEL_PATH}  |  threshold: {engine.THRESHOLDS['headings']}")
    print(f"Claude: {'ON' if client else 'OFF (no ANTHROPIC_API_KEY or --no-api)'}\n")

    local = await run("local", client, blocks)
    api = await run("api", client, blocks) if client else None

    w = args.width
    head = f"{'#':>4}  {'text':<{w}}  {'local':<7} {'conf':>6}  {'fallback':<8}"
    if api:
        head += f"  {'api':<7} same"
    print(head)
    print("-" * len(head))

    shown = 0
    for i, (b, lo) in enumerate(zip(blocks, local)):
        ap_label = api[i]["label"] if api else None
        if args.show == "headings" and lo["label"] == "Body" and ap_label in (None, "Body"):
            continue
        if args.show == "diff" and (not api or lo["label"] == ap_label):
            continue
        conf = "-" if lo["confidence"] is None else f"{lo['confidence']:.3f}"
        line = (f"{i:>4}  {cut(b.text, w):<{w}}  {lo['label']:<7} {conf:>6}  "
                f"{'YES' if lo['used_fallback'] else 'no':<8}")
        if api:
            line += f"  {ap_label:<7} {'✓' if lo['label'] == ap_label else '✗'}"
        print(line)
        shown += 1

    # ---- summary ----
    print(f"\nShown {shown} of {len(blocks)} lines.")
    print("Local labels :", dict(Counter(r["label"] for r in local)))
    n_fb = sum(r["used_fallback"] for r in local)
    print(f"Sent to Claude (local mode): {n_fb} of {len(blocks)} lines ({100 * n_fb / max(len(blocks), 1):.1f}%)")
    if api:
        print("API labels   :", dict(Counter(r["label"] for r in api)))
        # Claude never labels captions, so compare heading vs not-heading too.
        same = sum(lo["label"] == a["label"] for lo, a in zip(local, api))
        h = lambda lab: lab.startswith("H")
        same_h = sum(h(lo["label"]) == h(a["label"]) for lo, a in zip(local, api))
        print(f"Agreement local vs api: {same}/{len(blocks)} exact labels, "
              f"{same_h}/{len(blocks)} heading-vs-not")
        print("Note: the api column never says 'Caption' (Claude only finds headings).")


if __name__ == "__main__":
    asyncio.run(main())
