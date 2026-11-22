"""
clean_grammar_sentences.py  -  Grammar Step 3.

LanguageTool (offline, open source) se har sentence check karta hai.
  - 0 issues  -> sentences_<split>_clean.jsonl     (training/test ke liye "saaf" sentences)
  - issues    -> sentences_<split>_flagged.jsonl   (asli student ghaltiyan: error analysis ke kaam aayengi)

Run (brain/ml ke andar):
    pip install language_tool_python        # sirf pehli baar (Java 17+ chahiye)
    python3 clean_grammar_sentences.py --limit 300   # pehle chhota test
    python3 clean_grammar_sentences.py               # phir poora
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import language_tool_python


def rule_of(m):
    return getattr(m, "rule_id", None) or getattr(m, "ruleId", "UNKNOWN")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/grammar")
    ap.add_argument("--limit", type=int, default=0, help="har split se sirf itne sentences (test ke liye)")
    args = ap.parse_args()
    d = Path(args.dir)

    tool = language_tool_python.LanguageTool("en-US")
    rules = Counter()
    try:
        for split in ("train", "val", "test"):
            src = d / f"sentences_{split}.jsonl"
            items = [json.loads(l) for l in open(src, encoding="utf-8")]
            if args.limit:
                items = items[: args.limit]
            clean, flagged = [], []
            for n, it in enumerate(items, 1):
                matches = tool.check(it["text"])
                if matches:
                    it["lt_rules"] = sorted({rule_of(m) for m in matches})
                    rules.update(it["lt_rules"])
                    flagged.append(it)
                else:
                    clean.append(it)
                if n % 2000 == 0:
                    print(f"  {split}: {n}/{len(items)}", flush=True)
            for name, rows in (("clean", clean), ("flagged", flagged)):
                with open(d / f"sentences_{split}_{name}.jsonl", "w", encoding="utf-8") as fh:
                    for r in rows:
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            pct = 100 * len(flagged) / max(len(items), 1)
            print(f"{split:5s}: {len(items)} checked -> {len(clean)} clean, {len(flagged)} flagged ({pct:.0f}%)")
    finally:
        tool.close()

    print("\nSab se zyada aane wale LanguageTool rules:")
    for r, c in rules.most_common(15):
        print(f"  {c:6d}  {r}")


if __name__ == "__main__":
    main()