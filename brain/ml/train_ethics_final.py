import os, joblib
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.metrics import accuracy_score

D = "brain/ml/results/ethics"
TH, THRESH = 0.98, 0.4

def dedupe(X, groups=None):
    groups = np.zeros(len(X)) if groups is None else groups
    keep = np.ones(len(X), bool)
    for g in np.unique(groups):
        ids = np.where(groups == g)[0]
        S = X[ids] @ X[ids].T
        for a in range(len(ids)):
            if keep[ids[a]]:
                for b in np.where(S[a] > TH)[0]:
                    if b > a:
                        keep[ids[b]] = False
    return keep

def clean(test, train):
    return (test @ train.T).max(axis=1) <= TH

def stack(parts):
    return (np.concatenate([p[0] for p in parts]),
            np.concatenate([[p[1]] * len(p[0]) for p in parts]))

# ---- data ----
Xa = np.load(f"{D}/embeddings_all_reports.npy")
ma = pd.read_csv(f"{D}/meta_all_reports.csv")
k = dedupe(Xa, ma["group"].values)
Xa, ma = Xa[k], ma[k].reset_index(drop=True)
rng = np.random.RandomState(42)
photo = (ma["photo_score"] > 0.5).values
rest_ids = np.where(~photo)[0]
rest = rng.choice(rest_ids, size=min(2000, len(rest_ids)), replace=False)
idx = np.concatenate([np.where(photo)[0], rest])
X_safe, g_safe = Xa[idx], ma["group"].values[idx]

Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
X_sex = Xs[(ms["label"] == "sexual").values]
X_sex = X_sex[dedupe(X_sex)]

Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
is_val = (mw["group"] == "val").values
is_wv = mw["label"].isin(["weapons", "violence"]).values
wv_tr = Xw[is_wv & is_val]; wv_tr = wv_tr[dedupe(wv_tr)]
wv_te = Xw[is_wv & ~is_val]; wv_te = wv_te[clean(wv_te, wv_tr)]
neg7 = Xw[(mw["label"] == "negative").values]
print(f"Safe: {len(X_safe)} | Sexual (dedup): {len(X_sex)} | "
      f"Weapons train: {len(wv_tr)}, test (saaf): {len(wv_te)}")

# ---- 6-seed evaluation ----
rows = []
for seed in [1, 2, 3, 4, 5, 42]:
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
                  .split(X_safe, groups=g_safe))
    sex_tr, sex_te = train_test_split(X_sex, test_size=0.2, random_state=seed)
    s_te = X_safe[te][clean(X_safe[te], X_safe[tr])]
    x_te = sex_te[clean(sex_te, sex_tr)]
    Xtr, ytr = stack([(X_safe[tr], "safe"), (neg7, "safe"),
                      (sex_tr, "sexual"), (wv_tr, "weapons_violence")])
    Xte, yte = stack([(s_te, "safe"), (x_te, "sexual"), (wv_te, "weapons_violence")])
    clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
    p_unsafe = 1 - clf.predict_proba(Xte)[:, list(clf.classes_).index("safe")]
    flag, unsafe = p_unsafe >= THRESH, yte != "safe"
    rows.append(dict(seed=seed, n_test=len(yte),
                     test_acc=accuracy_score(yte, clf.predict(Xte)),
                     unsafe_recall=flag[unsafe].mean(),
                     false_alarm=flag[~unsafe].mean()))
df = pd.DataFrame(rows).round(4)
print(df.to_string(index=False))
print("\nMean:\n", df.drop(columns="seed").mean().round(4).to_string())
print("\nStd:\n", df.drop(columns="seed").std().round(4).to_string())
df.to_csv("brain/ml/results/ethics_final_metrics.csv", index=False)

# ---- final model: saara (saaf) data par ----
Xall, yall = stack([(X_safe, "safe"), (neg7, "safe"), (X_sex, "sexual"),
                    (wv_tr, "weapons_violence"), (wv_te, "weapons_violence")])
final = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xall, yall)
os.makedirs("brain/ml/models", exist_ok=True)
joblib.dump(final, "brain/ml/models/ethics_head_v3.joblib")
print("\nSaved: brain/ml/models/ethics_head_v3.joblib | classes:", list(final.classes_))