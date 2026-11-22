"""Embedding backends. 'fake' = deterministic, no downloads, for pipeline smoke tests only.
'real' = CLIP/SigLIP + MiniLM (+ BLIP) via transformers / sentence-transformers."""
import hashlib, json, pickle, re
from pathlib import Path
import numpy as np
import config


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _l2(x):
    x = np.asarray(x, dtype=np.float32)
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.maximum(n, 1e-8)


class FakeBackend:
    """Test-only. Text vec = sum of hashed word vectors (so word overlap -> similarity).
    Image vec = text vec of the FILENAME words (synthetic test images are named by topic)."""
    name = "fake"
    clip_name = "fake-clip"
    dim = 64

    def _word(self, w):
        seed = int(hashlib.md5(w.encode()).hexdigest()[:8], 16)
        return np.random.default_rng(seed).standard_normal(self.dim).astype(np.float32)

    def _text(self, s):
        ws = re.findall(r"[a-z0-9]+", (s or "").lower())
        if not ws:
            return np.zeros(self.dim, np.float32)
        return _l2(np.sum([self._word(w) for w in ws], axis=0))

    def clip_text(self, texts):
        return np.stack([self._text(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    mini_text = clip_text

    def clip_image(self, paths):
        return np.stack([self._text(Path(p).stem.replace("_", " ")) for p in paths])

    def blip_caption(self, paths):
        return [Path(p).stem.replace("_", " ") for p in paths]


class RealBackend:
    name = "real"

    def __init__(self, clip_name=None, mini_name=None, blip_name=None, device=None):
        import torch
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.clip_name = clip_name or config.CLIP_MODEL
        self.mini_name = mini_name or config.MINI_MODEL
        self.blip_name = blip_name or config.BLIP_MODEL
        self._clip = self._proc = self._mini = self._blip = self._blip_proc = None
        self.is_siglip = "siglip" in self.clip_name.lower()

    def _load_clip(self):
        if self._clip is None:
            from transformers import AutoModel, AutoProcessor
            self._clip = AutoModel.from_pretrained(self.clip_name).to(self.device).eval()
            self._proc = AutoProcessor.from_pretrained(self.clip_name)

    @staticmethod
    def _tensor(out):
        return out if hasattr(out, "shape") else out.pooler_output

    def clip_text(self, texts, bs=64):
        self._load_clip()
        res = []
        kw = dict(padding="max_length", max_length=64) if self.is_siglip else dict(padding=True, max_length=77)
        with self.torch.no_grad():
            for i in range(0, len(texts), bs):
                inp = self._proc(text=list(texts[i:i + bs]), return_tensors="pt", truncation=True, **kw).to(self.device)
                res.append(self._tensor(self._clip.get_text_features(**inp)).float().cpu().numpy())
        return _l2(np.concatenate(res)) if res else np.zeros((0, 512), np.float32)

    def clip_image(self, paths, bs=32):
        from PIL import Image
        self._load_clip()
        res = []
        with self.torch.no_grad():
            for i in range(0, len(paths), bs):
                ims = []
                for p in paths[i:i + bs]:
                    try:
                        ims.append(Image.open(p).convert("RGB"))
                    except Exception:
                        ims.append(Image.new("RGB", (224, 224)))
                inp = self._proc(images=ims, return_tensors="pt").to(self.device)
                res.append(self._tensor(self._clip.get_image_features(**inp)).float().cpu().numpy())
        return _l2(np.concatenate(res))

    def mini_text(self, texts, bs=128):
        if self._mini is None:
            from sentence_transformers import SentenceTransformer
            self._mini = SentenceTransformer(self.mini_name, device=self.device)
        return _l2(self._mini.encode(list(texts), batch_size=bs, show_progress_bar=False)) if texts else np.zeros((0, 384), np.float32)

    def blip_caption(self, paths):
        from PIL import Image
        if self._blip is None:
            from transformers import BlipForConditionalGeneration, BlipProcessor
            self._blip_proc = BlipProcessor.from_pretrained(self.blip_name)
            self._blip = BlipForConditionalGeneration.from_pretrained(self.blip_name).to(self.device).eval()
        out = []
        with self.torch.no_grad():
            for p in paths:
                try:
                    im = Image.open(p).convert("RGB")
                    inp = self._blip_proc(images=im, return_tensors="pt").to(self.device)
                    ids = self._blip.generate(**inp, max_new_tokens=30)
                    out.append(self._blip_proc.decode(ids[0], skip_special_tokens=True))
                except Exception:
                    out.append("")
        return out


def get_backend(kind, clip_name=None):
    if kind == "fake":
        return FakeBackend()
    return RealBackend(clip_name=clip_name)


class ImageEmbCache:
    """CLIP image embeddings cached on disk by file-content md5 (shared with ethics if you wish)."""

    def __init__(self, backend):
        safe = re.sub(r"[^A-Za-z0-9]+", "_", backend.clip_name)
        self.path = config.WORK_DIR / "cache" / f"clip_img__{safe}.pkl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self.d = pickle.load(open(self.path, "rb")) if self.path.exists() else {}

    def get(self, hashes, paths):
        todo = [(h, p) for h, p in zip(hashes, paths) if h not in self.d]
        todo = list({h: p for h, p in todo}.items())
        if todo:
            embs = self.backend.clip_image([p for _, p in todo])
            for (h, _), e in zip(todo, embs):
                self.d[h] = e
            pickle.dump(self.d, open(self.path, "wb"))
        return np.stack([self.d[h] for h in hashes])


class JsonCache:
    def __init__(self, name):
        self.path = config.WORK_DIR / "cache" / name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.d = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        self.path.write_text(json.dumps(self.d))
