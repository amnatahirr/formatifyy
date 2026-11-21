import json
import pandas as pd
import pyarrow.parquet as pq

path = "brain/ml/data/ethics/weapons_raw/validation-00000-of-00001.parquet"

# 1) naam mapping parquet ke metadata se
meta = pq.ParquetFile(path).schema_arrow.metadata or {}
raw = meta.get(b"huggingface")
names = None

def find_names(node):
    if isinstance(node, dict):
        if isinstance(node.get("names"), list):
            return node["names"]
        for v in node.values():
            r = find_names(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_names(v)
            if r:
                return r
    return None

if raw:
    names = find_names(json.loads(raw)["info"]["features"]["objects"])

if names:
    print("ID -> Name:")
    for i, n in enumerate(names):
        print(f"  {i}: {n}")
else:
    print("Naam mapping metadata mein nahi mili")

# 2) har category kitni images mein aati hai (image ke baghair)
df = pd.read_parquet(path, columns=["objects"])
img_count = {}
for obj in df["objects"]:
    for c in set(int(x) for x in obj["category"]):
        img_count[c] = img_count.get(c, 0) + 1

print("\nCategory -> kitni images mein:")
for c in sorted(img_count):
    label = names[c] if names and c < len(names) else "?"
    print(f"  {c} ({label}): {img_count[c]}")