import os
from collections import Counter
from PIL import Image

base = "brain/ml/data/ethics/raw"
files = sorted(f for f in os.listdir(base)
               if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))

print("Total:", len(files))
print("Pehle 8 naam:", files[:8])
print("Extensions:", dict(Counter(os.path.splitext(f)[1].lower() for f in files)))

bad, sizes = 0, []
for f in files:
    try:
        with Image.open(os.path.join(base, f)) as im:
            sizes.append(im.size)
    except Exception:
        bad += 1

print("Kharab/na khulne wali files:", bad)
if sizes:
    w = [s[0] for s in sizes]; h = [s[1] for s in sizes]
    print(f"Width: min {min(w)}, max {max(w)} | Height: min {min(h)}, max {max(h)}")