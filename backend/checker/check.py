import json
import os

TRAINING_DATA_PATH = os.path.join("checker", "training_data.json")

with open(TRAINING_DATA_PATH, "r", encoding="utf-8") as f:
    sections = json.load(f)

# Extract all headings
headings = [s["heading"] for s in sections if "heading" in s]

# Get **unique headings** and take the first 50
unique_headings = list(dict.fromkeys(headings))[:50]  # preserves order

print("First 50 headings:")
for i, h in enumerate(unique_headings, 1):
    print(f"{i}. {h}")