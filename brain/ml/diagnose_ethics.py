import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split

D = "brain/ml/results/ethics"
THRESH = 0.4
rng = np.random.RandomState(42)

Xa = np.load(f"{D}/embeddings_all_reports.npy")
ma = pd.read_csv(f"{D}/meta_all_reports.csv")
photo = (ma["photo_score"] > 0.5).values
rest = rng.choice(np.where(~photo)[0], size=2000, replace=False)
idx = np.concatenate([np.where(photo)[0], rest])
X_safe, g_safe, p_safe_paths = Xa[idx], ma["group"].values[idx], ma["path"].values[idx]

Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
X_sex = Xs[(ms["label"] == "sexual").values]
Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
is_val = (mw["group"] == "val").values
is_wv = mw["label"].isin(["weapons", "violence"]).values
wv_tr, neg7 = Xw[is_wv & is_val], Xw[(mw["label"] == "negative").values]

for seed in [2, 3, 5]:
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
                  .split(X_safe, groups=g_safe))
    sex_tr, _ = train_test_split(X_sex, test_size=0.2, random_state=seed)
    Xtr = np.concatenate([X_safe[tr], neg7, sex_tr, wv_tr])
    ytr = np.array(["safe"] * (len(tr) + len(neg7)) + ["sexual"] * len(sex_tr)
                   + ["wv"] * len(wv_tr))
    clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
    p_unsafe = 1 - clf.predict_proba(X_safe[te])[:, list(clf.classes_).index("safe")]
    flag = p_unsafe >= THRESH

    df = pd.DataFrame({"report": g_safe[te], "flag": flag, "p": p_unsafe,
                       "path": p_safe_paths[te]})
    print(f"\n===== seed {seed}: safe test images {len(df)}, galat alarm {flag.sum()} =====")
    by = df.groupby("report")["flag"].agg(["sum", "count"]).sort_values("sum", ascending=False)
    print(by.head(5).to_string())
    print("Sabse zyada shak wali 4 images:")
    for _, r in df.sort_values("p", ascending=False).head(4).iterrows():
        print(f"  p={r['p']:.2f}  {r['path']}")