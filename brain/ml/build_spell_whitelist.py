"""
build_spell_whitelist.py  -  spell-checker whitelist for the Grammar tab.

Report sentences (data/grammar/sentences_*.jsonl, fields text/report/idx) se
woh words nikaalta hai jo dictionary mein NAHI hain lekin kam az kam
--min_reports alag reports mein aate hain (technical terms: Kinect, Firebase, ...).
Yeh words spell-checker kabhi flag nahi karega.

Safety: agar kisi word ka 1-letter-door dictionary word maujood hai (e.g.
"recieve" -> "receive"), to woh shayad aam ghalti hai, us ke liye zyada reports
(--min_reports_typo) chahiye.

Default: sirf train + val reports (test reports evaluation ke liye alag rehte hain).

Run (brain/ml ke andar):
    python3 build_spell_whitelist.py
    python3 build_spell_whitelist.py --splits train val test   # test bhi shamil

Output: models/grammar_spell_whitelist.json
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from spellchecker import SpellChecker

WORD = re.compile(r"[A-Za-z][A-Za-z']*[A-Za-z]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/grammar")
    ap.add_argument("--splits", nargs="+", default=["train", "val"])
    ap.add_argument("--min_reports", type=int, default=3)
    ap.add_argument("--min_reports_typo", type=int, default=8)
    ap.add_argument("--out", default="models/grammar_spell_whitelist.json")
    args = ap.parse_args()

    reports_of = defaultdict(set)                    # word -> set(report)
    for sp in args.splits:
        for line in open(Path(args.dir) / f"sentences_{sp}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            for w in WORD.findall(r["text"]):
                reports_of[w.lower()].add(r["report"])

    spell = SpellChecker()
    unknown = spell.unknown(reports_of.keys())
    words, held_back = [], []
    for w in sorted(unknown):
        n = len(reports_of[w])
        if n < args.min_reports:
            continue
        near = spell.known(spell.edit_distance_1(w))
        if near and n < args.min_reports_typo:
            held_back.append((w, n, sorted(near)[:3]))
            continue
        words.append(w)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({
            "splits": args.splits,
            "min_reports": args.min_reports,
            "min_reports_typo": args.min_reports_typo,
            "words": words,
        }, fh, indent=1, ensure_ascii=False)

    print(f"unknown words seen: {len(unknown)}  -> whitelisted: {len(words)}")
    print(f"held back (look like typos of a dictionary word): {len(held_back)}")
    for w, n, near in held_back[:15]:
        print(f"   {w:20s} {n:3d} reports  ~ {', '.join(near)}")
    print("sample whitelist:", ", ".join(words[:40]))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
