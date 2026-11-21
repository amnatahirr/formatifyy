"""Medical hard negatives: ImageNet-1k ki medical classes ke CLIP embeddings.

Kyun: head ne needle/syringe wali medical images kabhi nahi dekhi thein, is liye
blood draw jaisi image ko 'weapons_violence' samajh leta tha. Ye images 'safe'
class mein jaati hain.

Source: HuggingFace mlnomad/imnet1k_<class> (ImageNet-1k, research/academic use).
Split: ImageNet ka train -> 80% train / 20% test, validation -> test.
Raw parquet files embeddings ke baad delete ho jaati hain (KEEP_RAW = False).

Repo root se: python brain/ml/extract_medical_embeddings.py
"""
import io, os, shutil
import numpy as np, pandas as pd, torch
from PIL import Image
from huggingface_hub import hf_hub_download
from transformers import CLIPModel, CLIPProcessor

OUT = "brain/ml/results/ethics"
RAW = "brain/ml/data/ethics/medical_raw"
KEEP_RAW = False
CLASSES = ["syringe", "stethoscope", "lab_coat_laboratory_coat", "oxygen_mask"]

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
rng = np.random.RandomState(42)


def embed(images):
    with torch.no_grad():
        out = model.get_image_features(**proc(images=images, return_tensors="pt"))
        if not torch.is_tensor(out):
            out = out.pooler_output
        if out.shape[-1] != 512:
            out = model.visual_projection(out)
        return (out / out.norm(dim=-1, keepdim=True)).numpy()


embs, rows = [], []
for cls in CLASSES:
    repo = f"mlnomad/imnet1k_{cls}"
    for part in ("train", "validation"):
        path = hf_hub_download(repo, f"data/{part}-00000-of-00001.parquet",
                               repo_type="dataset", local_dir=f"{RAW}/{cls}")
        df = pd.read_parquet(path)
        img_col = next(c for c in df.columns if "image" in c.lower())
        if part == "train":
            split = np.where(rng.rand(len(df)) < 0.8, "train", "test")
        else:
            split = np.array(["test"] * len(df))
        recs = df[img_col].tolist()
        for i in range(0, len(recs), 32):
            imgs, meta = [], []
            for j, r in enumerate(recs[i:i + 32], start=i):
                try:
                    raw = r["bytes"] if isinstance(r, dict) else r
                    imgs.append(Image.open(io.BytesIO(raw)).convert("RGB"))
                    meta.append((f"{cls}/{part}/{j}", cls, split[j]))
                except Exception:
                    pass
            if imgs:
                embs.append(embed(imgs)); rows += meta
        print(f"{cls} {part}: {len(df)} images | total {len(rows)}", flush=True)

np.save(f"{OUT}/embeddings_medical.npy", np.concatenate(embs))
meta = pd.DataFrame(rows, columns=["path", "label", "split"])
meta.to_csv(f"{OUT}/meta_medical.csv", index=False)
print(meta.groupby(["label", "split"]).size())

if not KEEP_RAW:
    shutil.rmtree(RAW, ignore_errors=True)
    print("Raw parquet files deleted:", RAW)
