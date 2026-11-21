import pandas as pd

PATHS = {
    "validation": "brain/ml/data/ethics/weapons_raw/validation-00000-of-00001.parquet",
    "test": "brain/ml/data/ethics/weapons_raw/test-00000-of-00001.parquet",
}
WEAPON = {0, 3, 4, 6, 7, 8, 9, 10, 12, 13, 14, 18, 19, 20, 23, 24, 25, 26, 28}
UNCERTAIN = {17, 21}
VIOLENCE = {1, 2, 15, 16, 27}

def group_of(cats):
    cats = set(int(c) for c in cats)
    if cats & WEAPON:
        return "weapon"
    if cats & UNCERTAIN:
        return "uncertain"
    if cats & VIOLENCE:
        return "violence_only"
    return "negative"

for split, path in PATHS.items():
    try:
        df = pd.read_parquet(path, columns=["objects"])
    except FileNotFoundError:
        print(split, ": file nahi mili, skip")
        continue
    groups = df["objects"].apply(lambda o: group_of(o["category"]))
    print(f"\n{split}: {len(df)} images")
    print(groups.value_counts().to_string())