"""
train_headings_v4.py  -  v4 heading model: v3 + numbering-strip augmentation.

Why: v3 learned "number at the start of the line => heading". Real unformatted
Word files often have headings with no numbers ("Background", "Data Collection").

What changes vs v3 (features are IDENTICAL, so the model is a drop-in):
  - Every TRAIN report is used twice: original, and a copy where the numbers
    are removed from heading lines ("1.1 Background" -> "Background").
    The copy is built per report BEFORE feature extraction, so the
    previous/next-line context is stripped too.
  - VAL is evaluated twice: original and stripped. The model is chosen on the
    average of both, so it cannot win by relying on numbers.
  - Only "heading or not" is judged. The level (H1/H2) comes from the admin's
    template, so it is not part of the score.
  - Gold sheet and test split are NEVER used for training or tuning.
  - Test split is touched only with --final (run once, at the very end).

Run (inside brain/ml, venv active, DYLD_FALLBACK_LIBRARY_PATH set):
    python train_headings_v4.py            # train + choose on val
    python train_headings_v4.py --final    # one-time test-split report, v3 vs v4
"""
import argparse
import csv
import json
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier

from train_headings import HERE, make_weights
from train_headings_v3 import load_sequences
from functions.heading_local import LABELS  # noqa: E402
from functions.heading_text import FEATURES_V3, text_context_features  # noqa: E402

HEAD_IDS = [i for i, l in enumerate(LABELS) if re.fullmatch(r"H\d", l)]

# "1.", "1.1", "1.1.2", "1)", "IV.", "a)", "Chapter 3:", "Section 2."
NUM = re.compile(
    r"^\s*(?:(?:chapter|section)\s+\d+[:.]?|\d+(?:\.\d+)*[.)]?|[ivxIVX]+[.)]|[A-Za-z][.)])\s+",
    re.IGNORECASE,
)


def strip_number(text):
    new = NUM.sub("", text, count=1).strip()
    return new if new else text


def stripped_copy(rows):
    """rows = [(idx, text, label)]; remove numbers from heading lines only."""
    return [
        (idx, strip_number(t) if re.fullmatch(r"H\d", lab) else t, lab)
        for idx, t, lab in rows
    ]


def xy_from(seqs):
    X, y = [], []
    for rows in seqs:
        if not rows:
            continue
        X += text_context_features([t for _, t, _ in rows])
        y += [LABELS.index(l) for _, _, l in rows]
    return np.asarray(X, dtype=float), np.asarray(y)


def head_prob(proba):
    """P(line is a heading) = sum of the H1/H2/H3... class probabilities. Level is ignored."""
    return proba[:, HEAD_IDS].sum(axis=1)


def summarize(name, y, pred):
    """Heading-vs-rest only (the template decides the level/style, not the model)."""
    t, p = np.isin(y, HEAD_IDS), np.isin(pred, HEAD_IDS)
    print(f"  {name:22s} heading precision {precision_score(t, p):.4f} | recall {recall_score(t, p):.4f} "
          f"| F1 {f1_score(t, p):.4f} | acc {(t == p).mean():.4f}")
    return f1_score(t, p)


def binary_threshold_table(proba, y, thresholds=(0.6, 0.7, 0.8, 0.9)):
    """Confidence = max(p, 1-p) of the heading/not-heading decision. Low confidence -> Claude."""
    p = head_prob(proba)
    true, pred = np.isin(y, HEAD_IDS), p >= 0.5
    conf, wrong = np.maximum(p, 1 - p), (p >= 0.5) != np.isin(y, HEAD_IDS)
    rows = []
    for t in thresholds:
        keep = conf >= t
        rows.append({
            "threshold": t,
            "sent_to_claude_pct": round(100 * float((~keep).mean()), 2),
            "accuracy_on_kept": round(float((pred[keep] == true[keep]).mean()), 4),
            "heading_f1_on_kept": round(float(f1_score(true[keep], pred[keep])), 4),
            "errors_caught_pct": round(100 * float((wrong & ~keep).sum() / max(wrong.sum(), 1)), 1),
        })
    return rows


def final_report(models_dir, reports):
    test = [r["rows"] for r in reports.values() if r["split"] == "test"]
    sets = {"test (numbered)": xy_from(test), "test (numbers removed)": xy_from([stripped_copy(r) for r in test])}
    for tag, fname in (("v3", "headings_xgb_v3.json"), ("v4", "headings_xgb_v4.json")):
        m = XGBClassifier()
        m.load_model(str(models_dir / fname))
        print(f"\n{tag}:")
        for name, (X, y) in sets.items():
            summarize(name, y, m.predict(X))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(HERE / "data/labels/headings_auto.jsonl"))
    ap.add_argument("--parsed", default=str(HERE / "data/parsed"))
    ap.add_argument("--models", default=str(HERE / "models"))
    ap.add_argument("--results", default=str(HERE / "results/headings_v4"))
    ap.add_argument("--final", action="store_true", help="one-time test-split report (v3 vs v4)")
    args = ap.parse_args()
    models_dir, results_dir = Path(args.models), Path(args.results)
    models_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    reports = load_sequences(Path(args.labels), Path(args.parsed))

    if args.final:
        final_report(models_dir, reports)
        return

    tr = [r["rows"] for r in reports.values() if r["split"] == "train"]
    va = [r["rows"] for r in reports.values() if r["split"] == "val"]
    Xtr, ytr = xy_from(tr + [stripped_copy(r) for r in tr])
    Xva, yva = xy_from(va)
    Xvs, yvs = xy_from([stripped_copy(r) for r in va])
    print(f"Loaded in {time.time() - t0:.0f}s | train {len(ytr)} rows (orig + stripped), "
          f"val {len(yva)} + {len(yvs)} rows")
    print("  train labels:", dict(Counter(LABELS[k] for k in ytr)))

    best = None
    for depth in (4, 6, 8):
        for scheme in ("balanced", "sqrt"):
            m = XGBClassifier(
                n_estimators=800, max_depth=depth, learning_rate=0.1,
                subsample=0.9, colsample_bytree=0.9, tree_method="hist",
                objective="multi:softprob", eval_metric="mlogloss",
                early_stopping_rounds=30, n_jobs=-1, random_state=42,
            )
            # early stopping on the stripped val set (the hard case)
            m.fit(Xtr, ytr, sample_weight=make_weights(ytr, scheme),
                  eval_set=[(Xvs, yvs)], verbose=False)
            f_o = f1_score(np.isin(yva, HEAD_IDS), head_prob(m.predict_proba(Xva)) >= 0.5)
            f_s = f1_score(np.isin(yvs, HEAD_IDS), head_prob(m.predict_proba(Xvs)) >= 0.5)
            score = (f_o + f_s) / 2
            print(f"  depth={depth} weights={scheme:8s} trees={m.best_iteration + 1:3d}  "
                  f"val heading-F1 numbered={f_o:.4f} stripped={f_s:.4f} avg={score:.4f}")
            if best is None or score > best[0]:
                best = (score, depth, scheme, m)

    score, depth, scheme, model = best
    print(f"\nChosen: depth={depth}, weights={scheme} (avg val heading-F1 {score:.4f})")
    print("\nVAL report (v4):")
    summarize("val numbered", yva, model.predict(Xva))
    summarize("val numbers removed", yvs, model.predict(Xvs))

    model.save_model(str(models_dir / "headings_xgb_v4.json"))
    imp = dict(sorted(zip(FEATURES_V3, map(float, model.feature_importances_)), key=lambda kv: -kv[1]))
    (models_dir / "headings_xgb_v4_meta.json").write_text(json.dumps({
        "labels": LABELS, "features": FEATURES_V3,
        "params": {"max_depth": depth, "weights": scheme, "n_estimators": int(model.best_iteration + 1)},
        "trained_on": "train split + numbering-stripped copies, auto labels, text+context features",
        "feature_importance": {k: round(v, 4) for k, v in imp.items()},
    }, indent=2))

    table = binary_threshold_table(model.predict_proba(Xvs), yvs)
    with open(results_dir / "threshold_table_val_stripped.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print("\nVAL threshold table (numbers removed, vs auto labels):")
    for r in table:
        print(f"  {r['threshold']:.2f} | {r['sent_to_claude_pct']:6.2f}% to Claude | acc rest {r['accuracy_on_kept']:.4f} "
              f"| heading-F1 rest {r['heading_f1_on_kept']:.4f} | errors caught {r['errors_caught_pct']:.1f}%")
    print("\nTop features:", ", ".join(f"{k} {v:.3f}" for k, v in list(imp.items())[:8]))
    print(f"Saved {models_dir / 'headings_xgb_v4.json'} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()