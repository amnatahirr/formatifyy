import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.metrics import classification_report, confusion_matrix

D = "brain/ml/results/ethics"
rng = np.random.RandomState(42)

# 1) Safe: apni reports
Xa = np.load(f"{D}/embeddings_all_reports.npy")
ma = pd.read_csv(f"{D}/meta_all_reports.csv")
photo = (ma["photo_score"] > 0.5).values
rest = np.where(~photo)[0]
rest = rng.choice(rest, size=min(2000, len(rest)), replace=False)
idx = np.concatenate([np.where(photo)[0], rest])
X_safe, g_safe = Xa[idx], ma["group"].values[idx]
photo_safe = photo[idx]
paths_safe = ma["path"].values[idx]

# 2) Sexual
Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
X_sex = Xs[(ms["label"] == "sexual").values]

# 3) Weapons dataset
Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
X_wea_tr = Xw[((mw["label"] == "weapons") & (mw["group"] == "val")).values]
X_wea_te = Xw[((mw["label"] == "weapons") & (mw["group"] == "test")).values]
X_vio = Xw[(mw["label"] == "violence").values]
X_neg7 = Xw[(mw["label"] == "negative").values]

# Split
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
tr, te = next(gss.split(X_safe, groups=g_safe))
sex_tr, sex_te = train_test_split(X_sex, test_size=0.2, random_state=42)
vio_tr, vio_te = train_test_split(X_vio, test_size=0.2, random_state=42)

def stack(parts):
    X = np.concatenate([p[0] for p in parts]); y = np.concatenate([[p[1]] * len(p[0]) for p in parts])
    return X, y

Xtr, ytr = stack([(X_safe[tr], "safe"), (X_neg7, "safe"), (sex_tr, "sexual"),
                  (X_wea_tr, "weapons"), (vio_tr, "violence")])
Xte, yte = stack([(X_safe[te], "safe"), (sex_te, "sexual"),
                  (X_wea_te, "weapons"), (vio_te, "violence")])

clf = LogisticRegression(max_iter=3000, class_weight="balanced")
clf.fit(Xtr, ytr)
pred = clf.predict(Xte)

print("Train:", len(Xtr), "| Test:", len(Xte))
print(classification_report(yte, pred, digits=3))
labels = list(clf.classes_)
print("Classes:", labels)
print(confusion_matrix(yte, pred, labels=labels))

# Safe photos jinko galti se unsafe kaha gaya
te_photo = photo_safe[te]
pred_safe = pred[:len(te)]
fp = te_photo & (pred_safe != "safe")
print(f"\nSafe photos in test: {te_photo.sum()} | galti se flag: {fp.sum()}")
proba = clf.predict_proba(X_safe[te])
for j in np.where(fp)[0][:15]:
    print(f"  {pred_safe[j]:9s} p={proba[j].max():.2f}  {paths_safe[te][j]}")