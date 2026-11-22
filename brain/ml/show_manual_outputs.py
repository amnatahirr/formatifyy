"""
show_manual_outputs.py - show the model's output next to the gold label for the manual test set,
to see where the model fails.

Run (inside brain/ml):
    python3 show_manual_outputs.py --csv data/grammar/eval/manual_label_done.csv --model models/t5_grammar_own

The CSV needs the columns: text, has_error, corrected (same as manual_label.csv).
If 'corrected' is empty the sentence is treated as correct.
Output: manual_outputs.csv (open it in Excel) plus a summary in the terminal.
"""
import argparse
import csv

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

PREFIX = "Fix grammar: "      # same prompt as in training
YES = {"1", "yes", "y", "true", "haan", "han", "ha", "x"}


def norm(s):
    return " ".join((s or "").split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--model", default="models/t5_grammar_own")
    ap.add_argument("--out", default="manual_outputs.csv")
    ap.add_argument("--beams", type=int, default=4)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    rows = [r for r in rows if norm(r.get("text"))]
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model).eval()

    outs = []
    for i in range(0, len(rows), 8):
        batch = [PREFIX + norm(r["text"]) for r in rows[i:i + 8]]
        enc = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=160)
        with torch.no_grad():
            gen = model.generate(**enc, num_beams=args.beams, max_new_tokens=128)
        outs.extend(tok.batch_decode(gen, skip_special_tokens=True))
        print(f"{min(i + 8, len(rows))}/{len(rows)}", end="\r")
    print()

    stats = {"has_error": 0, "fixed": 0, "changed_wrong": 0, "missed": 0, "clean": 0, "false_alarm": 0}
    result = []
    for r, out in zip(rows, outs):
        text = norm(r["text"])
        corr = norm(r.get("corrected"))
        flag = (r.get("has_error") or "").strip().lower() in YES or bool(corr and corr != text)
        gold = corr if flag else text
        out = norm(out)
        if flag:
            stats["has_error"] += 1
            if out == gold:
                verdict = "FIXED"
                stats["fixed"] += 1
            elif out == text:
                verdict = "MISSED"
                stats["missed"] += 1
            else:
                verdict = "CHANGED_WRONG"
                stats["changed_wrong"] += 1
        else:
            stats["clean"] += 1
            if out == text:
                verdict = "UNCHANGED_OK"
            else:
                verdict = "FALSE_ALARM"
                stats["false_alarm"] += 1
        result.append({"id": r.get("id", ""), "verdict": verdict, "input": text, "gold": gold, "model": out})

    with open(args.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "verdict", "input", "gold", "model"])
        w.writeheader()
        w.writerows(result)

    print(f"sentences with errors {stats['has_error']}: fixed {stats['fixed']} | "
          f"missed {stats['missed']} | changed wrong {stats['changed_wrong']}")
    print(f"correct sentences {stats['clean']}: false alarms {stats['false_alarm']}")
    for v in ("CHANGED_WRONG", "FALSE_ALARM", "MISSED"):
        shown = [x for x in result if x["verdict"] == v][:5]
        if shown:
            print(f"\n--- {v} (first {len(shown)}) ---")
            for x in shown:
                print(f"IN   : {x['input'][:140]}\nGOLD : {x['gold'][:140]}\nMODEL: {x['model'][:140]}\n")
    print(f"full list: {args.out}")


if __name__ == "__main__":
    main()