"""Central config for image-relevance pipeline.
Run all scripts from the PROJECT ROOT. Override any path with env vars."""
import os
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent

def _p(env, default):
    return Path(os.environ.get(env, default))

PARSED_DIR  = _p("IMGREL_PARSED_DIR", "data/parsed")        # folder with 265 report .jsonl files
IMAGES_DIR  = _p("IMGREL_IMAGES_DIR", "data/images")        # folder with extracted images
SPLITS_CSV  = _p("IMGREL_SPLITS_CSV", "data/splits.csv")    # report,group,split
WORK_DIR    = _p("IMGREL_WORK_DIR",   str(_BACKEND / ".cache" / "image_rel"))     # pairs, features, caches (gitignored!)
RESULTS_DIR = _p("IMGREL_RESULTS_DIR", "results/image_rel") # metrics, tables (safe to commit)
MODEL_PATH  = _p("IMGREL_MODEL_PATH", str(_ROOT / "brain" / "ml" / "models" / "image_rel_v1.joblib"))

CLIP_MODEL  = os.environ.get("IMGREL_CLIP_MODEL", "openai/clip-vit-base-patch32")
MINI_MODEL  = os.environ.get("IMGREL_MINI_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BLIP_MODEL  = os.environ.get("IMGREL_BLIP_MODEL", "Salesforce/blip-image-captioning-base")
CLAUDE_MODEL = os.environ.get("IMGREL_CLAUDE_MODEL", "claude-haiku-4-5-20251001")

SEED = 42
MIN_SIDE = 80            # drop icons/logos smaller than this (px)
MAX_ASPECT = 8.0         # drop banners / lines
DHASH_MAX_HAMMING = 3    # near-duplicate threshold (64-bit dHash)
N_HARD_NEG = 1           # hard negatives per positive (same report, other section)
N_EASY_NEG = 1           # easy negatives per positive (other report, same split)
SECTION_WORDS = 80       # words of section body kept as context
CAPTION_DROPOUT = 0.30   # training: hide caption features in 30% of rows
TARGET_LOCAL_ACC = 0.87  # accuracy wanted on rows NOT flagged for review (0.95 was unreachable: ~65% flagged)

for d in (WORK_DIR, RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
