import os

base = "brain/ml/data/ethics/raw"
for root, dirs, files in os.walk(base):
    imgs = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    if imgs:
        print(root, "->", len(imgs), "images")