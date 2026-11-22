import joblib
import numpy as np, pandas as pd

D = "brain/ml/results/ethics"
Xa = np.load(f"{D}/embeddings_all_reports.npy")
ma = pd.read_csv(f"{D}/meta_all_reports.csv")

# duplicates hata do (har report ke andar)
keep = np.ones(len(Xa), bool)
for g in ma["group"].unique():
    ids = np.where(ma["group"].values == g)[0]
    S = Xa[ids] @ Xa[ids].T
    for a in range(len(ids)):
        if keep[ids[a]]:
            for b in np.where(S[a] > 0.98)[0]:
                if b > a:
                    keep[ids[b]] = False
Xa, ma = Xa[keep], ma[keep].reset_index(drop=True)
photo = (ma["photo_score"] > 0.5).values
print(f"Safe images: {len(Xa)} | photo jaisi: {photo.sum()}\n")

for name, path in [("v3", "brain/ml/models/ethics_head_v3.joblib"),
                   ("v5_clean", "brain/ml/models/ethics_head_v5_clean.joblib")]:
    clf = joblib.load(path)
    p = 1 - clf.predict_proba(Xa)[:, list(clf.classes_).index("safe")]
    print(f"{name:9s} flagged (p>=0.6): sab {np.mean(p >= 0.6):6.2%} | "
          f"photo jaisi {np.mean(p[photo] >= 0.6):6.2%} | "
          f"photo se bahar {np.mean(p[~photo] >= 0.6):6.2%}")
    if name == "v5_clean":
        top = np.argsort(-p)[:12]
        print("\nv5_clean ki sabse zyada shak wali 12 (tumhari apni images):")
        for i in top:
            print(f"  p={p[i]:.2f}  {ma['path'][i]}")