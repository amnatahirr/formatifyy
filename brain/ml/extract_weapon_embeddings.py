import io, random
import numpy as np, pandas as pd, torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

random.seed(42)
OUT = "brain/ml/results/ethics"
VAL = "brain/ml/data/ethics/weapons_raw/validation-00000-of-00001.parquet"
TEST = "brain/ml/data/ethics/weapons_raw/test-00000-of-00001.parquet"
WEAPON = {0, 3, 4, 6, 7, 8, 9, 10, 12, 13, 14, 18, 19, 20, 23, 24, 25, 26, 28}
UNCERTAIN = {17, 21}
VIOLENCE = {1, 2, 15, 16, 27}

def group_of(cats):
    cats = set(int(c) for c in cats)
    if cats & WEAPON: return "weapons"
    if cats & UNCERTAIN: return "uncertain"
    if cats & VIOLENCE: return "violence"
    return "negative"

def load(path, split):
    df = pd.read_parquet(path, columns=["image_id", "image", "objects"])
    df["label"] = df["objects"].apply(lambda o: group_of(o["category"]))
    df["split"] = split
    return df

val, test = load(VAL, "val"), load(TEST, "test")

def pick(df, label, n=None):
    d = df[df["label"] == label]
    return d if n is None or len(d) <= n else d.sample(n, random_state=42)

chosen = pd.concat([
    pick(val, "weapons", 800), pick(val, "violence"), pick(val, "negative"),
    pick(test, "weapons", 400),
])
print(chosen.groupby(["split", "label"]).size())

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

embs, rows = [], []
recs = chosen.to_dict("records")
BATCH = 32
for i in range(0, len(recs), BATCH):
    imgs, meta = [], []
    for r in recs[i:i+BATCH]:
        try:
            raw = r["image"]["bytes"] if isinstance(r["image"], dict) else r["image"]
            imgs.append(Image.open(io.BytesIO(raw)).convert("RGB"))
            meta.append((f'{r["split"]}_{r["image_id"]}', r["label"], r["split"]))
        except Exception:
            pass
    if not imgs:
        continue
    with torch.no_grad():
        out = model.get_image_features(**proc(images=imgs, return_tensors="pt"))
        if not torch.is_tensor(out):
            out = out.pooler_output
        if out.shape[-1] != 512:
            out = model.visual_projection(out)
        e = out / out.norm(dim=-1, keepdim=True)
    embs.append(e.numpy()); rows += meta
    print(f"{len(rows)}/{len(recs)} done")

np.save(f"{OUT}/embeddings_weapons.npy", np.concatenate(embs))
pd.DataFrame(rows, columns=["path", "label", "group"]).to_csv(f"{OUT}/meta_weapons.csv", index=False)
print("Saved weapons embeddings")