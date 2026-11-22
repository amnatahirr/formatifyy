import numpy as np
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score, precision_score, recall_score

CAP_FEATS = ["clip_img_cap", "mini_cap_head", "mini_cap_sec", "has_caption", "cap_len"]


def mask_caption(X):
    X = X.copy()
    for c in CAP_FEATS:
        X[c] = 0
    return X


def best_threshold(y, s):
    """threshold maximising macro-F1 (call on VAL only)."""
    best, bt = -1, 0.5
    for t in np.unique(np.round(s, 3)):
        f = f1_score(y, s >= t, average="macro")
        if f > best:
            best, bt = f, float(t)
    return bt


def basic(y, s, t):
    p = (s >= t).astype(int)
    return {"auc": round(float(roc_auc_score(y, s)), 4) if len(set(y)) > 1 else None,
            "macro_f1": round(float(f1_score(y, p, average="macro")), 4),
            "acc": round(float(accuracy_score(y, p)), 4),
            "prec_relevant": round(float(precision_score(y, p, zero_division=0)), 4),
            "rec_relevant": round(float(recall_score(y, p, zero_division=0)), 4)}


def band_table(y, s, t, widths=np.arange(0.0, 0.41, 0.02)):
    """Rows near threshold go to Claude. Returns list of dicts (like heading threshold table)."""
    rows = []
    for w in widths:
        out = (s < t - w) | (s > t + w)
        n_out = int(out.sum())
        acc = float(((s[out] >= t).astype(int) == y[out]).mean()) if n_out else float("nan")
        rows.append({"half_width": round(float(w), 2), "pct_to_claude": round(100 * (1 - n_out / len(s)), 1),
                     "local_acc": round(acc, 4)})
    return rows


def pick_band(rows, target):
    valid = [r for r in rows if r["local_acc"] == r["local_acc"]]
    ok = [r for r in valid if r["local_acc"] >= target]
    if ok:
        return ok[0], True
    return max(valid, key=lambda r: (r["local_acc"], -r["pct_to_claude"])), False


def rank_metrics(df, score):
    """df has img_uid,label. recall@1 and MRR: does the true section rank first among all sections?"""
    d = df[["img_uid", "label"]].copy()
    d["s"] = score
    r1, mrr, n = 0, 0.0, 0
    for _, g in d.groupby("img_uid"):
        if g.label.sum() != 1 or len(g) < 2:
            continue
        s = g.s.values
        pos = s[g.label.values == 1][0]
        rank = 1 + int((s > pos).sum()) + 0.5 * int(((s == pos).sum() - 1))  # ties split fairly
        r1 += rank <= 1.5
        mrr += 1.0 / rank
        n += 1
    return {"recall_at_1": round(r1 / n, 4) if n else None, "mrr": round(mrr / n, 4) if n else None, "n_images": n}
