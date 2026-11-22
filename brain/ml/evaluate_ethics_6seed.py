import json, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

D = "brain/ml/results/ethics"
OUT = "brain/ml/results"
THRESH = 0.4

def load():
    rng = np.random.RandomState(42)
    Xa = np.load(f"{D}/embeddings_all_reports.npy")
    ma = pd.read_csv(f"{D}/meta_all_reports.csv")
    photo = (ma["photo_score"] > 0.5).values
    rest = rng.choice(np.where(~photo)[0], size=2000, replace=False)
    idx = np.concatenate([np.where(photo)[0], rest])
    Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
    Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
    is_val = (mw["group"] == "val").values
    is_wv = mw["label"].isin(["weapons", "violence"]).values
    return dict(X_safe=Xa[idx], g_safe=ma["group"].values[idx],
                X_sex=Xs[(ms["label"] == "sexual").values],
                wv_tr=Xw[is_wv & is_val], wv_te=Xw[is_wv & ~is_val],
                neg7=Xw[(mw["label"] == "negative").values])

def stack(parts):
    X = np.concatenate([p[0] for p in parts])
    y = np.concatenate([[p[1]] * len(p[0]) for p in parts])
    return X, y

def run(d, seed):
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
                  .split(d["X_safe"], groups=d["g_safe"]))
    sex_tr, sex_te = train_test_split(d["X_sex"], test_size=0.2, random_state=seed)
    Xtr, ytr = stack([(d["X_safe"][tr], "safe"), (d["neg7"], "safe"),
                      (sex_tr, "sexual"), (d["wv_tr"], "weapons_violence")])
    Xte, yte = stack([(d["X_safe"][te], "safe"), (sex_te, "sexual"),
                      (d["wv_te"], "weapons_violence")])
    clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
    p_safe = clf.predict_proba(Xte)[:, list(clf.classes_).index("safe")]
    flag = (1 - p_safe) >= THRESH
    unsafe = yte != "safe"
    row = dict(seed=seed,
               train_acc=accuracy_score(ytr, clf.predict(Xtr)),
               test_acc=accuracy_score(yte, clf.predict(Xte)),
               unsafe_recall=float(flag[unsafe].mean()),
               false_alarm=float(flag[~unsafe].mean()))
    return row, clf, Xte, yte

d = load()
rows = []
for seed in [1, 2, 3, 4, 5, 42]:
    row, clf, Xte, yte = run(d, seed)
    rows.append(row)
    if seed == 42:
        final = (clf, Xte, yte)

df = pd.DataFrame(rows).round(4)
print(df.to_string(index=False))
print("\nMean:\n", df.drop(columns="seed").mean().round(4).to_string())
print("\nStd (kitna hilta hai):\n", df.drop(columns="seed").std().round(4).to_string())

clf, Xte, yte = final
pred = clf.predict(Xte)
labels = list(clf.classes_)
cm = confusion_matrix(yte, pred, labels=labels)

os.makedirs(OUT, exist_ok=True)
df.to_csv(f"{OUT}/ethics_stability.csv", index=False)
with open(f"{OUT}/ethics_report.json", "w") as f:
    json.dump(classification_report(yte, pred, output_dict=True), f, indent=2)

fig, ax = plt.subplots(figsize=(5, 4))
ax.imshow(cm, cmap="Blues")
ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=20)
ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
for i in range(len(labels)):
    for j in range(len(labels)):
        ax.text(j, i, cm[i, j], ha="center", va="center")
ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title("Image Ethics (seed 42)")
plt.tight_layout(); plt.savefig(f"{OUT}/ethics_confusion_matrix.png", dpi=150)
print("\nSaved: ethics_stability.csv, ethics_report.json, ethics_confusion_matrix.png in", OUT)