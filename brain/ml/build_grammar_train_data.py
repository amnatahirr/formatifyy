"""
build_grammar_train_data.py - Grammar Step 6: build "wrong -> correct" training pairs.

Input : data/grammar/sentences_train_clean.jsonl, sentences_val_clean.jsonl   (Step 3)
Output: data/grammar/train/train_pairs_own.jsonl, val_pairs_own.jsonl
        each line: {"src": corrupted (or identical) sentence, "tgt": correct sentence, "errors": [...]}

Two kinds of pairs:
  1. wrong -> correct   (1 or 2 synthetic errors injected into a clean sentence)
  2. correct -> same    (so the model learns to leave correct sentences alone)

Run (inside brain/ml):
    python3 build_grammar_train_data.py
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

from grammar_noise import OPS

# Sampling weight per error type. The model was weak on articles, commas and plural/singular
# on the manual test (real student errors), so those get more weight; error types the model
# already learned well (capitalization, repeated_word, spelling) get less.
WEIGHTS = {"article_missing": 3.0, "article_wrong": 1.5, "verb_agreement": 2.0, "comma_missing": 3.0,
           "spelling": 0.8, "repeated_word": 0.4, "preposition": 1.0, "plural_singular": 3.0,
           "capitalization": 0.4}


def load(p):
    return [json.loads(line) for line in open(p, encoding="utf-8")]


def corrupt_balanced(sentence, rng, n_errors):
    """Inject n_errors errors; error types are sampled by WEIGHTS among those that apply."""
    cur, used = sentence, []
    names = list(OPS)
    for _ in range(12):                         # a few attempts
        if len(used) == n_errors:
            break
        name = rng.choices(names, weights=[WEIGHTS[n] for n in names])[0]
        if name in used:
            continue
        out = OPS[name](cur, rng)
        if out and out != cur:
            cur, used = out, used + [name]
    if not used or cur == sentence:
        return None
    return cur, used


def make_pairs(items, rng, unchanged_frac, two_err_frac, copies):
    pairs, types = [], Counter()
    for it in items:
        s = it["text"]
        for _ in range(copies):
            n = 2 if rng.random() < two_err_frac else 1
            res = corrupt_balanced(s, rng, n)
            if res:
                bad, kinds = res
                pairs.append({"src": bad, "tgt": s, "errors": kinds})
                types.update(kinds)
        if rng.random() < unchanged_frac:
            pairs.append({"src": s, "tgt": s, "errors": []})
    rng.shuffle(pairs)
    return pairs, types


def dump(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/grammar")
    ap.add_argument("--seed", type=int, default=7)            # different from the test set seed (123)
    ap.add_argument("--copies", type=int, default=1, help="corrupted versions per sentence")
    ap.add_argument("--unchanged_frac", type=float, default=0.4,
                    help="fraction of sentences also added as correct->same pairs")
    ap.add_argument("--two_err_frac", type=float, default=0.3)
    ap.add_argument("--n_val", type=int, default=3000)
    args = ap.parse_args()

    d = Path(args.dir)
    out = d / "train"
    out.mkdir(exist_ok=True)
    rng = random.Random(args.seed)

    train = [x for x in load(d / "sentences_train_clean.jsonl") if 6 <= len(x["text"].split()) <= 60]
    val = [x for x in load(d / "sentences_val_clean.jsonl") if 6 <= len(x["text"].split()) <= 60]
    rng.shuffle(val)
    val = val[: args.n_val]

    tr_pairs, tr_types = make_pairs(train, rng, args.unchanged_frac, args.two_err_frac, args.copies)
    va_pairs, _ = make_pairs(val, rng, args.unchanged_frac, args.two_err_frac, 1)

    # Sanity check: no test sentence may appear in the training targets
    # (already removed in Step 2, but we verify again).
    test_keys = {x["text"].lower() for x in load(d / "sentences_test.jsonl")}
    leak = sum(1 for p in tr_pairs if p["tgt"].lower() in test_keys)
    assert leak == 0, f"{leak} training pairs have a target that is also in the test set!"

    dump(out / "train_pairs_own.jsonl", tr_pairs)
    dump(out / "val_pairs_own.jsonl", va_pairs)

    bad_pairs = [p for p in tr_pairs if p["errors"]]
    n_same = len(tr_pairs) - len(bad_pairs)
    print(f"train pairs: {len(tr_pairs)}  (wrong->correct {len(bad_pairs)}, correct->same {n_same})")
    print(f"val pairs  : {len(va_pairs)}")
    print("error types (train):", dict(tr_types))
    print("\n8 examples:")
    for p in rng.sample(bad_pairs, min(8, len(bad_pairs))):
        print(f"  WRONG  : {p['src'][:110]}\n  CORRECT: {p['tgt'][:110]}   {p['errors']}\n")
    print(f"saved in {out}/")


if __name__ == "__main__":
    main()