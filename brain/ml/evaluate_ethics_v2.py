import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.metrics import accuracy_score

D = "brain/ml/results/ethics"
THRESH = 0.4
DUP = 0.98

def dedupe(X, groups):
    keep = np.ones(len(X), bool)
    for g in np.unique(groups):
        ids = np.where(groups == g)[0]
        S = X[ids] @ X[ids].T
        for a in range(len(ids)):
            if not keep[ids[a]]:
                continue
            for b in np.where(S[a] > DUP)[0]:
                if b > a:
                    keep[ids[b]] = False
    return keep

Xa = np.load(f"{D}/embeddings_all_reports.npy")
ma = pd.read_csv(f"{D}/meta_all_reports.csv")
keep = dedupe(Xa, ma["group"].values)
print(f"Safe images: {len(Xa)} -> {keep.sum()} (duplicates hataye: {(~keep).sum()})")
cs03 = ma["group"].str.startswith("CS03_A Suspect")
print(f"CS03 Suspect Monitoring: {cs03.sum()} -> {(cs03 & keep).sum()}")
Xa, ma = Xa[keep], ma[keep].reset_index(drop=True)

rng = np.random.RandomState(42)
photo = (ma["photo_score"] > 0.5).values
rest_ids = np.where(~photo)[0]
rest = rng.choice(rest_ids, size=min(2000, len(rest_ids)), replace=False)
idx = np.concatenate([np.where(photo)[0], rest])
X_safe, g_safe = Xa[idx], ma["group"].values[idx]

Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
X_sex = Xs[(ms["label"] == "sexual").values]
Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
is_val = (mw["group"] == "val").values
is_wv = mw["label"].isin(["weapons", "violence"]).values
wv_tr, wv_te = Xw[is_wv & is_val], Xw[is_wv & ~is_val]
neg7 = Xw[(mw["label"] == "negative").values]

def stack(parts):
    return (np.concatenate([p[0] for p in parts]),
            np.concatenate([[p[1]] * len(p[0]) for p in parts]))

rows = []
for seed in [1, 2, 3, 4, 5, 42]:
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
                  .split(X_safe, groups=g_safe))
    sex_tr, sex_te = train_test_split(X_sex, test_size=0.2, random_state=seed)
    Xtr, ytr = stack([(X_safe[tr], "safe"), (neg7, "safe"),
                      (sex_tr, "sexual"), (wv_tr, "weapons_violence")])
    Xte, yte = stack([(X_safe[te], "safe"), (sex_te, "sexual"),
                      (wv_te, "weapons_violence")])
    clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
    p_unsafe = 1 - clf.predict_proba(Xte)[:, list(clf.classes_).index("safe")]
    flag, unsafe = p_unsafe >= THRESH, yte != "safe"
    rows.append(dict(seed=seed,
                     train_acc=accuracy_score(ytr, clf.predict(Xtr)),
                     test_acc=accuracy_score(yte, clf.predict(Xte)),
                     unsafe_recall=flag[unsafe].mean(),
                     false_alarm=flag[~unsafe].mean()))

df = pd.DataFrame(rows).round(4)
print(df.to_string(index=False))
print("\nMean:\n", df.drop(columns="seed").mean().round(4).to_string())
print("\nStd:\n", df.drop(columns="seed").std().round(4).to_string())
df.to_csv("brain/ml/results/ethics_stability_dedup.csv", index=False)