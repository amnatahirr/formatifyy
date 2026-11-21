import os, sys, io, base64
import numpy as np, pandas as pd, torch, joblib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from functions.local_vision import decode_base64_image, _load_clip, _device

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
D = os.path.join(ROOT, "brain", "ml", "results", "ethics")

meta = pd.read_csv(os.path.join(D, "meta_all_reports.csv"))
X = np.load(os.path.join(D, "embeddings_all_reports.npy"))
head = joblib.load(os.path.join(HERE, "ml_weights", "ethics_head_v2.joblib"))
classes = [str(c) for c in head.classes_]
print("Head classes:", classes)

@torch.inference_mode()
def backend_embedding(image):
    processor, model = _load_clip()
    inputs = processor(images=image, return_tensors="pt").to(_device)
    out = model.get_image_features(**inputs)
    print("   raw type:", type(out).__name__) if not torch.is_tensor(out) else None
    if not torch.is_tensor(out):
        out = out.pooler_output
    if out.shape[-1] != 512:
        out = model.visual_projection(out)
    out = out / out.norm(dim=-1, keepdim=True)
    return out.cpu().numpy()

rng = np.random.RandomState(1)
for i in rng.choice(len(meta), 8, replace=False):
    path = os.path.join(ROOT, meta["path"][i])
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    emb = backend_embedding(decode_base64_image(b64, for_inference=True))
    cos = float(emb[0] @ X[i])
    probs = dict(zip(classes, head.predict_proba(emb)[0].round(3)))
    print(f"{os.path.basename(path):14s} cos={cos:.4f}  p_unsafe={1 - probs['safe']:.3f}")