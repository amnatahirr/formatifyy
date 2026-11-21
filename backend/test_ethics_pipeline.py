import os, sys, base64, random, asyncio
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import functions.image_ethics as ie

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "brain", "ml", "data", "images")

paths = [os.path.join(r, f) for r, _, fs in os.walk(BASE)
         for f in fs if f.lower().endswith((".png", ".jpg", ".jpeg"))]
random.seed(3)
picked = random.sample(paths, 6)

def make_img(i, p):
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return SimpleNamespace(image_id=f"img_{i}", page_number=i + 1, base64=b64)

batch = SimpleNamespace(images=[make_img(i, p) for i, p in enumerate(picked)])

async def main():
    print("\n=== TEST 1: asli model, safe images ===")
    issues = await ie.check_image_ethics(None, batch)
    print("Flagged issues:", len(issues), "(0 hona chahiye)")

    print("\n=== TEST 2: head ko majboor karke 'unsafe' banana (sirf format check) ===")
    real = ie.predict_unsafe
    ie.predict_unsafe = lambda b64: {"p_unsafe": 0.95, "top_class": "weapons_violence", "probs": {}}
    issues = await ie.check_image_ethics(None, SimpleNamespace(images=batch.images[:1]))
    ie.predict_unsafe = real
    print("Flagged issues:", len(issues))
    for k in ("function", "image_id", "page", "ethics_category", "confidence", "_replace_image"):
        print(f"  {k}: {issues[0].get(k)}")

asyncio.run(main())