# ml/generate_dataset.py
# ONE-LINE FIX: numbered is merged into bullet in normalize_label()
# This fixes the "numbered: 1% precision" problem caused by only 0.2% of
# training data being numbered.  After this fix, retrain with:
#   python ml/train.py

import sys
import os
import csv
import glob
import docx
import fitz  # PyMuPDF

# Fix import path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from formatter.rules import detect_line_type


# ---------------------------
# Configuration
# ---------------------------
FOLDER_PATHS = [
    "ML/dataset_sources/formatted",
    "ML/dataset_sources/unformatted"
]

OUTPUT_CSV = "dataset.csv"

# ---------------------------
# Helper functions
# ---------------------------
def docx_to_text(file_path):
    doc = docx.Document(file_path)
    return [para.text for para in doc.paragraphs]

def pdf_to_text(file_path):
    text_lines = []
    doc = fitz.open(file_path)
    for page in doc:
        page_text = page.get_text()
        if page_text:
            text_lines.extend(page_text.split("\n"))
    return text_lines


# ---------------------------
# Normalize labels
# KEY FIX: merge "numbered" into "bullet"
# Numbered lists are formatted identically to bullets in paragraph_formatter.py
# and the model only has 1,306 numbered rows vs 575,988 total → 0.2% → broken.
# The rule engine in predictor.py already catches numbered via regex BEFORE ML,
# so the ML model never needs to predict "numbered" anyway.
# ---------------------------
def normalize_label(label):
    if label in ["heading1", "heading2", "heading3"]:
        return "heading"
    if label == "numbered":          # ← THE FIX (one line)
        return "bullet"
    return label


# ---------------------------
# Collect all lines
# ---------------------------
lines = []
total_files = 0

for folder in FOLDER_PATHS:
    all_files = glob.glob(os.path.join(folder, "*.*"))
    total_files += len(all_files)

    for file_path in all_files:
        print("Processing:", os.path.basename(file_path))
        ext = os.path.splitext(file_path)[1].lower()
        file_lines = []

        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                file_lines = f.read().split("\n")

        elif ext == ".docx":
            file_lines = docx_to_text(file_path)

        elif ext == ".pdf":
            file_lines = pdf_to_text(file_path)

        else:
            print(f"⚠️ Skipping unsupported file: {file_path}")
            continue

        lines.extend(file_lines)

print(f"✅ Found {len(lines)} lines from {total_files} files in {FOLDER_PATHS}")

# ---------------------------
# Generate dataset
# ---------------------------
dataset = []
prev_type = None

for line in lines:
    cleaned_line = line.strip()

    if not cleaned_line:
        continue

    raw_label = detect_line_type(cleaned_line, prev_type)
    label = normalize_label(raw_label)

    dataset.append([cleaned_line, label])
    prev_type = label


# ---------------------------
# Save dataset.csv
# ---------------------------
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["text", "label"])
    writer.writerows(dataset)

print(f"✅ Dataset generated: {OUTPUT_CSV} with {len(dataset)} rows")
print("Classes in dataset:")
from collections import Counter
counts = Counter(row[1] for row in dataset)
for cls, cnt in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {cnt:>8,}  {cls}")
print("\nNext step: python ml/train.py")
