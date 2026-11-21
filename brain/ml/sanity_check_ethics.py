import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.metrics import classification_report, confusion_matrix

OUT = "brain/ml/results/ethics"
X = np.load(f"{OUT}/embeddings.npy")
meta = pd.read_csv(f"{OUT}/meta.csv")
assert len(X) == len(meta), "embeddings aur meta ki length alag hai"
y = (meta["label"] == "sexual").astype(int).values

safe_idx = np.where(y == 0)[0]
sex_idx = np.where(y == 1)[0]

gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
tr, te = next(gss.split(safe_idx, groups=meta["group"].values[safe_idx]))
safe_train, safe_test = safe_idx[tr], safe_idx[te]
sex_train, sex_test = train_test_split(sex_idx, test_size=0.2, random_state=42)

train = np.concatenate([safe_train, sex_train])
test = np.concatenate([safe_test, sex_test])

clf = LogisticRegression(max_iter=2000, class_weight="balanced")
clf.fit(X[train], y[train])
pred = clf.predict(X[test])

print("Train:", len(train), "| Test:", len(test))
print(classification_report(y[test], pred, target_names=["safe", "sexual"], digits=3))
print("Confusion matrix (rows=asli, cols=predicted):")
print(confusion_matrix(y[test], pred))