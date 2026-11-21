import os, random
import numpy as np, pandas as pd, torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

SEXUAL_DIR = "brain/ml/data/ethics/raw"
SAFE_DIR = "brain/ml/data/images"
OUT = "brain/ml/results/ethics"
N_SAFE = 2000
os.makedirs(OUT, exist_ok=True)
random.seed(42)

exts = (".png", ".jpg", ".jpeg", ".webp")

sexual = [(os.path.join(SEXUAL_DIR, f), "sexual", "scraped")
          for f in sorted(os.listdir(SEXUAL_DIR)) if f.lower().endswith(exts)]

safe_all = []
for root, _, files in os.walk(SAFE_DIR):
    report = os.path.basename(root)
    for f in files:
        if f.lower().endswith(exts):
            safe_all.append((os.path.join(root, f), "safe", report))
safe = random.sample(safe_all, min(N_SAFE, len(safe_all)))

items = sexual + safe
print("Sexual:", len(sexual), "| Safe:", len(safe))

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

embs, rows = [], []
BATCH = 32
for i in range(0, len(items), BATCH):
    imgs, meta = [], []
    for path, label, group in items[i:i+BATCH]:
        try:
            imgs.append(Image.open(path).convert("RGB"))
            meta.append((path, label, group))
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
    embs.append(e.numpy())
    rows += meta
    print(f"{len(rows)}/{len(items)} done")

np.save(f"{OUT}/embeddings.npy", np.concatenate(embs))
pd.DataFrame(rows, columns=["path", "label", "group"]).to_csv(f"{OUT}/meta.csv", index=False)
print("Saved:", f"{OUT}/embeddings.npy", "and", f"{OUT}/meta.csv")