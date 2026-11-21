import os
import numpy as np, pandas as pd, torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

BASE = "brain/ml/data/images"
OUT = "brain/ml/results/ethics"
LIMIT = None   # pehle test ke liye 500 likh sakti ho, phir None
exts = (".png", ".jpg", ".jpeg", ".webp")

items = []
for root, _, files in os.walk(BASE):
    group = os.path.basename(root)
    for f in sorted(files):
        if f.lower().endswith(exts):
            items.append((os.path.join(root, f), group))
if LIMIT:
    items = items[:LIMIT]
print("Total images:", len(items))

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

def to_tensor(out, proj):
    if not torch.is_tensor(out):
        out = out.pooler_output
    if out.shape[-1] != 512:
        out = proj(out)
    return out / out.norm(dim=-1, keepdim=True)

photo_prompts = ["a photo of a person", "a photo of a person's face",
                 "a group photo of people", "a photograph of a real place or object"]
other_prompts = ["a screenshot of a software application", "a diagram or flowchart",
                 "a chart or graph", "a table of data", "a page of text", "a logo"]
prompts = photo_prompts + other_prompts

with torch.no_grad():
    t = model.get_text_features(**proc(text=prompts, return_tensors="pt", padding=True))
    text_emb = to_tensor(t, model.text_projection)

embs, rows, photo_scores = [], [], []
BATCH = 32
for i in range(0, len(items), BATCH):
    imgs, meta = [], []
    for path, group in items[i:i+BATCH]:
        try:
            imgs.append(Image.open(path).convert("RGB")); meta.append((path, group))
        except Exception:
            pass
    if not imgs:
        continue
    with torch.no_grad():
        out = model.get_image_features(**proc(images=imgs, return_tensors="pt"))
        e = to_tensor(out, model.visual_projection)
        probs = (100 * e @ text_emb.T).softmax(dim=-1)
        ps = probs[:, :len(photo_prompts)].sum(dim=-1)
    embs.append(e.numpy()); rows += meta; photo_scores += ps.tolist()
    if (i // BATCH) % 20 == 0:
        print(f"{len(rows)}/{len(items)} done")

np.save(f"{OUT}/embeddings_all_reports.npy", np.concatenate(embs))
df = pd.DataFrame(rows, columns=["path", "group"])
df["photo_score"] = photo_scores
df.to_csv(f"{OUT}/meta_all_reports.csv", index=False)

for th in (0.5, 0.7, 0.9):
    print(f"photo_score > {th}: {(df['photo_score'] > th).sum()} images")
print("\nTop 10 reports (photo wali images ki tadaad, score > 0.7):")
print(df[df["photo_score"] > 0.7]["group"].value_counts().head(10).to_string())