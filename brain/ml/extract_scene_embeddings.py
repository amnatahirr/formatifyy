"""Outdoor / real-world hard negatives: Places365 scene photos ke CLIP embeddings.

Kyun: weapons data zyada tar asli duniya ki photos (CCTV, bahar ke scenes) hain,
aur safe class mein aisi aam photos kam thin. Is liye model dashcam, CCTV frame,
drone/jahaz aur farsh jaisi harmless photos ko 'weapons_violence' keh deta tha.
Ye images 'safe' class mein jaati hain.

Source: HuggingFace rumenguin/places365-val (Places365 validation, 100 images per
scene; academic/research use). 37 aam scenes, kul 3,700 images (~48 MB).
Split: har scene ki 70% train, 30% test (alag 'scene test' ke liye).
Raw images embeddings ke baad delete ho jaati hain (KEEP_RAW = False).

Repo root se: python brain/ml/extract_scene_embeddings.py
"""
import os, shutil
import numpy as np, pandas as pd, torch
from PIL import Image
from huggingface_hub import snapshot_download
from transformers import CLIPModel, CLIPProcessor

OUT = "brain/ml/results/ethics"
RAW = "brain/ml/data/ethics/scenes_raw"
KEEP_RAW = False
SCENES = [
    "airfield", "alley", "bazaar-outdoor", "bridge", "bus_station-indoor", "campus",
    "classroom", "computer_room", "construction_site", "corridor", "courtyard",
    "crosswalk", "downtown", "driveway", "field_road", "garage-indoor",
    "garage-outdoor", "gas_station", "highway", "hospital_room", "kitchen",
    "lecture_room", "living_room", "lobby", "market-outdoor", "office",
    "operating_room", "parking_garage-indoor", "parking_lot", "playground",
    "residential_neighborhood", "runway", "science_museum", "server_room", "sky",
    "street", "train_station-platform",
]

snapshot_download("rumenguin/places365-val", repo_type="dataset", local_dir=RAW,
                  allow_patterns=[f"images/{s}/*" for s in SCENES])

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
for scene in SCENES:
    folder = os.path.join(RAW, "images", scene)
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".png")))
    split = np.where(rng.rand(len(files)) < 0.7, "train", "test")
    for i in range(0, len(files), 32):
        imgs, meta = [], []
        for j in range(i, min(i + 32, len(files))):
            try:
                imgs.append(Image.open(os.path.join(folder, files[j])).convert("RGB"))
                meta.append((f"{scene}/{files[j]}", scene, split[j]))
            except Exception:
                pass
        if imgs:
            embs.append(embed(imgs)); rows += meta
    print(f"{scene}: {len(files)} images | total {len(rows)}", flush=True)

np.save(f"{OUT}/embeddings_scenes.npy", np.concatenate(embs))
meta = pd.DataFrame(rows, columns=["path", "label", "split"])
meta.to_csv(f"{OUT}/meta_scenes.csv", index=False)
print(meta["split"].value_counts().to_string())

if not KEEP_RAW:
    shutil.rmtree(RAW, ignore_errors=True)
    print("Raw images deleted:", RAW)
