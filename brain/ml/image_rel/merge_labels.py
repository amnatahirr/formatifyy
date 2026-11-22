"""Merge labels.csv (row,your_label) from the labeling tool into gold_sheet.csv.
Run from project root (PowerShell):
  python merge_labels.py brain/ml/data/image_rel/gold_sheet.csv "$env:USERPROFILE\\Downloads\\labels.csv"
"""
import sys
import pandas as pd
gold = pd.read_csv(sys.argv[1], dtype=str).fillna("")
lab = pd.read_csv(sys.argv[2], dtype=str).fillna("")
m = dict(zip(lab["row"], lab["your_label"]))
gold["your_label"] = gold["row"].map(m).fillna("")
gold.to_csv(sys.argv[1], index=False)
print("labeled:", (gold["your_label"].isin(["0", "1"])).sum(), "| not sure (?):", (gold["your_label"] == "?").sum(),
      "| empty:", (gold["your_label"] == "").sum())
