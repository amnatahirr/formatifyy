import os
from collections import Counter

base = "brain/ml/data/images"
exts = Counter()
total = 0

for folder in sorted(os.listdir(base))[:5]:
    p = os.path.join(base, folder)
    if os.path.isdir(p):
        files = os.listdir(p)
        print(folder, "->", len(files), "files, examples:", files[:2])

for root, _, files in os.walk(base):
    for f in files:
        exts[os.path.splitext(f)[1].lower()] += 1
        total += 1

print("\nSub-folders:", len([d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]))
print("Total images:", total)
print("File types:", dict(exts))