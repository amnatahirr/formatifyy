import pandas as pd

path = "brain/ml/data/ethics/weapons_raw/validation-00000-of-00001.parquet"
df = pd.read_parquet(path)

print("Rows:", len(df))
print("Columns:", list(df.columns))
print("Dtypes:\n", df.dtypes)

# image column ko print nahi karna, sirf baqi columns ka pehla record
non_image = [c for c in df.columns if c.lower() != "image"]
print("\nPehle 3 records (image ke baghair):")
print(df[non_image].head(3).to_string())

for c in non_image:
    try:
        print(f"\nUnique values in '{c}':", df[c].astype(str).value_counts().head(15).to_dict())
    except Exception:
        pass