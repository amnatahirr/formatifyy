import numpy as np, pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split

D = "brain/ml/results/ethics"
SEED = 42

def dedupe(X, groups, th=0.98):
    keep = np.ones(len(X), bool)
    for g in np.unique(groups):
        ids = np.where(groups == g)[0]
        S = X[ids] @ X[ids].T
        for a in range(len(ids)):
            if keep[ids[a]]:
                for b in np.where(S[a] > th)[0]:
                    if b > a:
                        keep[ids[b]] = False
    return keep

def report(name, test, train):
    mx = (test @ train.T).max(axis=1)
    print(f"{name:22s} test={len(test):5d} | >0.98: {np.mean(mx > 0.98):6.1%} | "
          f">0.95: {np.mean(mx > 0.95):6.1%} | median: {np.median(mx):.3f}")

Xa = np.load(f"{D}/embeddings_all_reports.npy")
ma = pd.read_csv(f"{D}/meta_all_reports.csv")
keep = dedupe(Xa, ma["group"].values)
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

tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
              .split(X_safe, groups=g_safe))
sex_tr, sex_te = train_test_split(X_sex, test_size=0.2, random_state=SEED)

print("Test image ki sabse milti-julti TRAIN image kitni milti hai:\n")
report("Safe (alag reports)", X_safe[te], X_safe[tr])
report("Sexual", sex_te, sex_tr)
report("Weapons/Violence", wv_te, wv_tr)
print("\nWeapons val ke andar apne aap mein duplicates:")
S = wv_tr @ wv_tr.T; np.fill_diagonal(S, 0)
print(f"   >0.98: {np.mean(S.max(axis=1) > 0.98):.1%}")