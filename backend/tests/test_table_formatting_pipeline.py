"""
Verification for template-driven table formatting pipeline.
Run from backend/:  python test_table_formatting_pipeline.py
"""

from __future__ import annotations

import os
import sys
import tempfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.table_formatting_service import run_table_formatting_pipeline
from services.table_caption_service import detect_captions_for_tables, find_caption_near_table
from services.table_config import get_table_format_config


def _add_table(doc: Document, rows, caption: str | None = None, *, caption_above: bool = True):
    if caption and caption_above:
        p = doc.add_paragraph(caption)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            table.rows[r_i].cells[c_i].text = str(val)
    if caption and not caption_above:
        p = doc.add_paragraph(caption)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return table


def build_sample_docx(path: str) -> None:
    doc = Document()
    doc.add_heading("1 Introduction", level=1)
    doc.add_paragraph("Results are shown in Table 1.")
    _add_table(
        doc,
        [["Metric", "Value"], ["Accuracy", "0.92"], ["Latency", "12"]],
        "table 1: Performance metrics",
        caption_above=True,
    )

    doc.add_heading("2 Methods", level=1)
    doc.add_paragraph("See Table 2.1 for hyperparameters.")
    _add_table(
        doc,
        [["Param", "Setting"], ["lr", "0.001"], ["batch", "32"]],
        "Table 2: Hyperparameters",
        caption_above=True,
    )
    # Missing caption
    _add_table(
        doc,
        [["A", "B"], ["1", "2"], ["3", "4"]],
        None,
    )
    doc.add_paragraph("Broken ref to Table 99 should be flagged.")
    doc.save(path)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="fmt_tbl_")
    src = os.path.join(tmp, "sample.docx")
    out1 = os.path.join(tmp, "out1.docx")
    out2 = os.path.join(tmp, "out2.docx")
    build_sample_docx(src)

    rules_global = {
        "table_numbering_scheme": "global",
        "table_caption_format_pattern": "Table {n}: {description}",
        "table_caption_position": "above",
        "include_lot": True,
        "table_require_caption": True,
        "table_require_intext_reference": False,
        "list_of_tables_format": "Table {n}: {description}",
        "table_style": {
            "font_name": "Times New Roman",
            "font_size": 12,
            "header_bold": True,
            "header_bg": "D6E4F0",
            "banded_rows": True,
            "border_style": "academic_standard",
            "header_row_shading": True,
            "alignment_on_page": "center",
        },
    }

    r1 = run_table_formatting_pipeline(src, out1, rules_global)
    assert r1["status"] in ("success", "no_tables"), r1
    assert r1["total_tables"] == 3, r1
    # Missing caption should have been created
    assert r1["caption_missing_count"] == 0, r1["captions"]

    nums1 = [a["n"] for a in r1["numbering"]]
    assert nums1 == [1, 2, 3], nums1
    assert all(a.get("caption_updated") for a in r1["numbering"]), r1["numbering"]

    # Idempotent
    r2 = run_table_formatting_pipeline(out1, out2, rules_global)
    nums2 = [a["n"] for a in r2["numbering"]]
    assert nums2 == nums1, (nums1, nums2)

    refs = r1["references"]
    broken_nums = {b["number"] for b in refs["broken_references"]}
    assert "99" in broken_nums, refs

    lot = r1.get("list_of_tables") or {}
    assert lot.get("lot_added") is True, lot
    assert lot.get("lot_entry_count", 0) >= 3, lot

    # Caption still above after formatting
    doc = Document(out1)
    body_tables = list(doc.tables)
    assert len(body_tables) >= 3
    cap, pos, text = find_caption_near_table(doc, body_tables[0])
    assert cap is not None and pos == "above", (pos, text)
    assert "Table" in (text or cap.text or "")

    # Chapter scheme + caption below
    rules_ch = dict(rules_global)
    rules_ch["table_numbering_scheme"] = "chapter"
    rules_ch["table_caption_format_pattern"] = "Table {chapter}.{n}: {description}"
    rules_ch["table_caption_position"] = "below"
    rules_ch["list_of_tables_format"] = "Table {chapter}.{n}: {description}"
    out3 = os.path.join(tmp, "out3.docx")
    r3 = run_table_formatting_pipeline(src, out3, rules_ch)
    chapters = [(a["chapter"], a["n"]) for a in r3["numbering"]]
    assert chapters[0][0] == 1 and chapters[0][1] == 1, chapters
    assert chapters[1][0] == 2, chapters

    doc3 = Document(out3)
    cap3, pos3, _ = find_caption_near_table(doc3, doc3.tables[0])
    assert pos3 == "below", (pos3, cap3.text if cap3 else None)
    assert "1.1" in (cap3.text or "") or "Table 1.1" in (cap3.text or ""), cap3.text

    cfg = get_table_format_config(rules_global)
    assert cfg["table_style"]["font_size"] == 12

    print("PASS: table formatting pipeline checks")
    print(f"  tmp={tmp}")
    print(f"  global_numbers={nums1}")
    print(f"  chapter_pairs={chapters}")
    print(f"  lot={lot}")
    print(f"  broken_refs={broken_nums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
