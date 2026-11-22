"""
prepare_correction_batches.py - build numbered batches of flagged TRAIN sentences that can be pasted
into Claude to get corrected versions (silver labels for fine-tuning).

Only sentences from the train split are used. Sentences that also appear in the test set are removed.

Run (inside brain/ml):
    python3 prepare_correction_batches.py --n 2500 --batch_size 60

Output:
    data/grammar/llm/selected.jsonl          one line per selected sentence (batch, num, text, report, idx)
    data/grammar/llm/batches/batch_001.txt   prompt + numbered sentences, ready to copy into Claude
    data/grammar/llm/answers/                save each Claude answer here as batch_001.txt (same name)

IMPORTANT: run this only once. Re-running reshuffles the sentences and would misalign saved answers,
so the script refuses to overwrite an existing selected.jsonl unless you pass --force.
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

PROMPT = """Correct the grammar of each numbered sentence below.
Rules:
- Make minimal edits only: articles (a/an/the), prepositions, verb agreement, singular/plural, spelling, and punctuation (commas, missing full stops, capitalization).
- Do not rephrase, shorten, or change technical terms, names, or meaning.
- If a sentence is already correct, return it unchanged.
- Return exactly {n} lines, in the same order, formatted as: number. corrected sentence
- Put all {n} lines inside one code block. No explanations, no extra text.

SENTENCES:
"""


def load(p):
    return [json.loads(line) for line in open(p, encoding="utf-8")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/grammar")
    ap.add_argument("--n", type=int, default=2500, help="how many sentences to select")
    ap.add_argument("--batch_size", type=int, default=60)
    ap.add_argument("--per_report", type=int, default=25, help="max sentences taken from one report")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    d = Path(args.dir)
    out_dir = d / "llm"
    sel_path = out_dir / "selected.jsonl"
    if sel_path.exists() and not args.force:
        raise SystemExit(f"{sel_path} already exists. Re-running would misalign saved answers. Use --force to overwrite.")
    (out_dir / "batches").mkdir(parents=True, exist_ok=True)
    (out_dir / "answers").mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    test_keys = {x["text"].lower() for x in load(d / "sentences_test.jsonl")}

    pool, seen = [], set()
    for x in load(d / "sentences_train_flagged.jsonl"):
        text = " ".join(x["text"].split())
        key = text.lower()
        if not (6 <= len(text.split()) <= 50) or key in test_keys or key in seen:
            continue
        seen.add(key)
        pool.append({"text": text, "report": x.get("report"), "idx": x.get("idx")})
    rng.shuffle(pool)

    chosen, per = [], Counter()
    for x in pool:
        if per[x["report"]] < args.per_report:
            chosen.append(x)
            per[x["report"]] += 1
        if len(chosen) == args.n:
            break

    rows = []
    for i, x in enumerate(chosen):
        rows.append({"batch": i // args.batch_size + 1, "num": i % args.batch_size + 1, **x})

    with open(sel_path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_batches = rows[-1]["batch"] if rows else 0
    for b in range(1, n_batches + 1):
        items = [r for r in rows if r["batch"] == b]
        body = PROMPT.format(n=len(items)) + "\n".join(f"{r['num']}. {r['text']}" for r in items) + "\n"
        (out_dir / "batches" / f"batch_{b:03d}.txt").write_text(body, encoding="utf-8")

    print(f"flagged train sentences available: {len(pool)}")
    print(f"selected: {len(rows)} sentences from {len(per)} reports -> {n_batches} batches of up to {args.batch_size}")
    print(f"batches : {out_dir / 'batches'}")
    print(f"save Claude's answers in: {out_dir / 'answers'} (batch_001.txt, batch_002.txt, ...)")


if __name__ == "__main__":
    main()