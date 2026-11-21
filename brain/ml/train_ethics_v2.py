import os
import numpy as np, pandas as pd, joblib, torch
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from transformers import CLIPModel, CLIPProcessor

D = "brain/ml/results/ethics"
rng = np.random.RandomState(42)

Xa = np.load(f"{D}/embeddings_all_reports.npy")
ma = pd.read_csv(f"{D}/meta_all_reports.csv")
photo = (ma["photo_score"] > 0.5).values
rest = rng.choice(np.where(~photo)[0], size=2000, replace=False)
idx = np.concatenate([np.where(photo)[0], rest])
X_safe, g_safe = Xa[idx], ma["group"].values[idx]

Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
X_sex = Xs[(ms["label"] == "sexual").values]

Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
is_val = (mw["group"] == "val").values
is_wv = mw["label"].isin(["weapons", "violence"]).values
X_wv_tr = Xw[is_wv & is_val]
X_wv_te = Xw[is_wv & ~is_val]
X_neg7 = Xw[(mw["label"] == "negative").values]

tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
              .split(X_safe, groups=g_safe))
sex_tr, sex_te = train_test_split(X_sex, test_size=0.2, random_state=42)

def stack(parts):
    X = np.concatenate([p[0] for p in parts])
    y = np.concatenate([[p[1]] * len(p[0]) for p in parts])
    return X, y

Xtr, ytr = stack([(X_safe[tr], "safe"), (X_neg7, "safe"), (sex_tr, "sexual"),
                  (X_wv_tr, "weapons_violence")])
Xte, yte = stack([(X_safe[te], "safe"), (sex_te, "sexual"),
                  (X_wv_te, "weapons_violence")])

clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
pred = clf.predict(Xte)
print("Train:", len(Xtr), "| Test:", len(Xte))
print(classification_report(yte, pred, digits=3))
print(clf.classes_)
print(confusion_matrix(yte, pred, labels=clf.classes_))

# ---- Binary: safe vs unsafe, kai thresholds ----
unsafe = yte != "safe"
p_unsafe = 1 - clf.predict_proba(Xte)[:, list(clf.classes_).index("safe")]
print("\nTRAINED HEAD (binary)")
print("threshold | unsafe recall | safe galat alarm")
for T in (0.3, 0.4, 0.5, 0.6, 0.7):
    f = p_unsafe >= T
    print(f"   {T:.1f}    |    {f[unsafe].mean():.3f}      |   {f[~unsafe].mean():.3f}")
band = (p_unsafe > 0.4) & (p_unsafe < 0.6)
print(f"Claude fallback (0.4 se 0.6) mein aane wali images: {band.mean():.1%}")

# ---- Baseline: CLIP zero-shot (usi test set par) ----
good = ["a screenshot of a software application", "a diagram or flowchart",
        "a chart or graph", "a table of data", "a normal photo of people",
        "a normal photograph for a university report"]
bad = ["a nude or sexually explicit image", "a violent or gory image",
       "a photo of a weapon", "a photo of a gun or a knife"]
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
with torch.no_grad():
    t = model.get_text_features(**proc(text=good + bad, return_tensors="pt", padding=True))
    if not torch.is_tensor(t):
        t = t.pooler_output
    if t.shape[-1] != 512:
        t = model.text_projection(t)
    t = (t / t.norm(dim=-1, keepdim=True)).numpy()
logits = 100 * Xte @ t.T
probs = np.exp(logits - logits.max(1, keepdims=True))
probs /= probs.sum(1, keepdims=True)
zs = probs[:, len(good):].sum(1) >= 0.5
print("\nCLIP ZERO-SHOT (binary)")
print(f"unsafe recall: {zs[unsafe].mean():.3f} | safe galat alarm: {zs[~unsafe].mean():.3f}")

os.makedirs("brain/ml/models", exist_ok=True)
joblib.dump(clf, "brain/ml/models/ethics_head_v2.joblib")
print("\nSaved: brain/ml/models/ethics_head_v2.joblib")