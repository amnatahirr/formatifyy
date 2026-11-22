"""STAGE 5: final numbers on the TEST split (+ hand-labelled gold set if you made one).
Thresholds come from VAL only. Writes results/image_rel/{test_results.csv, gold_results.csv, comparison.md}.
Run:  python brain/ml/image_rel/s5_evaluate.py"""
import json
import numpy as np, pandas as pd, joblib
import config
from s2_features import FEATS
from metrics_util import *

LIVE_THR = 0.22  # current live CLIP-cosine threshold in image_relevance.py


def md(df):
    df = df.copy(); df.columns = [str(c) for c in df.columns]
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if (isinstance(v, float) and v != v) or v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def main():
    b = joblib.load(config.MODEL_PATH)
    model, t_dec, w = b["model"], b["t_dec"], b["band_half_width"]
    va = pd.read_csv(config.WORK_DIR / "features_val.csv")
    te = pd.read_csv(config.WORK_DIR / "features_test.csv")
    rk_path = config.WORK_DIR / "features_rank_test.csv"
    rk = pd.read_csv(rk_path) if rk_path.exists() else None
    t_clip = best_threshold(va.label.values, va.clip_img_head.values)
    t_cap = best_threshold(va.label.values, va.mini_cap_head.values)

    methods = {
        f"CLIP zero-shot cosine (thr {t_clip:.3f}, val-tuned)": (lambda X: X.clip_img_head.values, t_clip),
        f"CLIP zero-shot cosine (thr {LIVE_THR}, current live)": (lambda X: X.clip_img_head.values, LIVE_THR),
        f"MiniLM caption~heading only (thr {t_cap:.3f})": (lambda X: X.mini_cap_head.values, t_cap),
        "Trained scorer (caption available)": (lambda X: model.predict_proba(X[FEATS])[:, 1], t_dec),
        "Trained scorer (caption hidden)": (lambda X: model.predict_proba(mask_caption(X[FEATS]))[:, 1], t_dec),
    }
    rows = []
    y = te.label.values
    for name, (fn, t) in methods.items():
        s = fn(te)
        r = {"method": name, **basic(y, s, t)}
        if rk is not None:
            r.update(rank_metrics(rk, fn(rk)))
        if name.startswith("Trained"):
            out = (s < t - w) | (s > t + w)
            r["pct_to_claude"] = round(100 * (1 - out.mean()), 1)
            r["local_acc"] = round(float(((s[out] >= t).astype(int) == y[out]).mean()), 4) if out.any() else None
        rows.append(r)
    res = pd.DataFrame(rows)
    res.to_csv(config.RESULTS_DIR / "test_results.csv", index=False)
    s = methods["Trained scorer (caption available)"][0](te)
    cm = pd.crosstab(pd.Series(y, name="actual"), pd.Series((s >= t_dec).astype(int), name="pred"))
    cm.to_csv(config.RESULTS_DIR / "confusion_matrix_test.csv")
    # hard-negative breakdown
    brk = []
    for nt in ("hard", "easy"):
        m = (te.neg_type == nt) | (te.neg_type == "pos")
        brk.append({"negatives": nt, **basic(y[m], s[m], t_dec)})
    md_out = [f"# Image relevance results (test split)\n\nThreshold {t_dec:.3f} and band ±{w} were chosen on the validation split only.\n",
              md(res), "\n\n## Confusion matrix (test, trained scorer)\n", md(cm.reset_index()),
              "\n\n## Easy vs hard negatives (trained scorer)\n", md(pd.DataFrame(brk))]
    print(md(res))

    gp = config.WORK_DIR / "gold_sheet.csv"
    if gp.exists():
        g = pd.read_csv(gp)
        g = g[g.your_label.astype(str).isin(["0", "1", "0.0", "1.0"])]
        if len(g) >= 20:
            g["gold"] = g.your_label.astype(float).astype(int)
            g = g.merge(te, on="pair_id", how="inner")
            yg = g.gold.values
            grows = []
            for name, (fn, t) in methods.items():
                grows.append({"method": name, **basic(yg, fn(g), t)})
            cp = config.WORK_DIR / "gold_claude.csv"
            if cp.exists():
                c = pd.read_csv(cp).merge(g[["pair_id", "gold"]], on="pair_id")
                if len(c):
                    pc = c.claude_relevant.astype(int).values
                    grows.append({"method": "Claude API (image + heading + caption)", **basic(c.gold.values, pc.astype(float), 0.5)})
            noise = round(float((g.gold.values == g.label.values).mean()), 4)
            gr = pd.DataFrame(grows)
            gr.to_csv(config.RESULTS_DIR / "gold_results.csv", index=False)
            md_out += [f"\n\n## Hand-labelled gold set (n={len(g)})\n", md(gr),
                       f"\n\nAgreement between automatic (placement) labels and hand labels: {noise:.1%} "
                       f"(an estimate of label noise; lower = noisier training labels).\n"]
            print("\nGOLD (n=%d)\n" % len(g) + md(gr) + f"\nauto-label vs hand-label agreement: {noise:.1%}")
        else:
            print(f"\n[INFO] gold sheet has only {len(g)} labelled rows (need >=20); skipped.")
    else:
        print("\n[INFO] no gold_sheet.csv yet (run s4_gold_sheet.py and label it).")
    (config.RESULTS_DIR / "comparison.md").write_text("\n".join(md_out))
    print(f"\n[OK] wrote {config.RESULTS_DIR/'comparison.md'}")


if __name__ == "__main__":
    main()
