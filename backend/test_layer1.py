"""
test_layer1.py  — run from your backend/ directory
Usage:
    python test_layer1.py path/to/your_file.docx
    python test_layer1.py path/to/your_file.pdf
    python test_layer1.py path/to/your_file.txt
"""

import sys
import json
from services.document_block_extractor import extract_blocks

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_layer1.py <file_path>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"\n{'='*60}")
    print(f"  Extracting blocks from: {path}")
    print(f"{'='*60}\n")

    blocks = extract_blocks(path)

    # ── Summary ──────────────────────────────────────────────────────────────
    types = {}
    for b in blocks:
        types[b["type"]] = types.get(b["type"], 0) + 1

    print(f"Total blocks : {len(blocks)}")
    for btype, count in sorted(types.items()):
        print(f"  {btype:<15}: {count}")

    print()

    # ── Show headings ─────────────────────────────────────────────────────────
    headings = [b for b in blocks if b["type"] == "heading"]
    print(f"{'─'*60}")
    print(f"  HEADINGS ({len(headings)} found)")
    print(f"{'─'*60}")
    for h in headings:
        indent = "  " * ((h["level"] or 1) - 1)
        size   = h["metadata"]["font_size"]
        bold   = "B" if h["metadata"]["is_bold"] else " "
        size_s = f"{size:5.1f}pt" if size else "  n/a  "
        print(f"  [{bold}] {size_s}  L{h['level']}  {indent}{h['text']}")

    print()

    # ── Show first 5 paragraphs ───────────────────────────────────────────────
    paras = [b for b in blocks if b["type"] == "paragraph"][:5]
    print(f"{'─'*60}")
    print(f"  FIRST 5 PARAGRAPHS")
    print(f"{'─'*60}")
    for p in paras:
        preview = p["text"][:120] + ("…" if len(p["text"]) > 120 else "")
        print(f"  [{p['index']:3}] {preview}")

    print()

    # ── Dump full JSON to file ────────────────────────────────────────────────
    out_path = "layer1_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(blocks, f, indent=2, ensure_ascii=False)
    print(f"Full output saved to: {out_path}")
    print()


if __name__ == "__main__":
    main()