"""
test_layer3.py — run from backend/
Tests the full Layer 1 + 2 + 3 pipeline.

Usage:
    python test_layer3.py <file_path> <template_id>
    python test_layer3.py services/test_doc.docx 1

    # Or run the built-in demo (no file needed):
    python test_layer3.py
"""

from __future__ import annotations
import sys
import json

# ── Terminal colors ───────────────────────────────────────────────────────────
R  = "\033[91m"   # red    — error
Y  = "\033[93m"   # yellow — warning
B  = "\033[94m"   # blue   — info
G  = "\033[92m"   # green  — pass
W  = "\033[97m"   # white
DIM= "\033[2m"
RST= "\033[0m"

SEV_COLOR = {"error": R, "warning": Y, "info": B}

STATUS_COLOR = {
    "found":       G,
    "missing":     R,
    "wrong_order": Y,
    "empty":       Y,
}

LAYER_COLOR = {
    "exact":    G,
    "synonym":  B,
    "fuzzy":    Y,
    "semantic": "\033[95m",
}


def print_report(report: dict, filename: str = "", template_name: str = ""):
    w = 72
    print(f"\n{'═'*w}")
    print(f"  LAYER 3 — STRUCTURE CHECK REPORT")
    if filename:
        print(f"  File     : {filename}")
    if template_name:
        print(f"  Template : {template_name}")
    print(f"{'═'*w}")

    # ── Score & status ────────────────────────────────────────────────────────
    score  = report["score"]
    status = report["status"]
    sc     = G if status == "pass" else R
    bar_filled = int(score / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    print(f"\n  Score  : {sc}{score:3d}/100  {bar}{RST}")
    print(f"  Status : {sc}{status.upper()}{RST}\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    s = report["summary"]
    print(f"{'─'*w}")
    print(f"  {'Required sections':<30} {s['total_required']}")
    print(f"  {'Found correctly':<30} {G}{s['found']}{RST}")
    print(f"  {'Missing (required)':<30} {(R if s['missing'] else DIM)}{s['missing']}{RST}")
    print(f"  {'Wrong order':<30} {(Y if s['wrong_order'] else DIM)}{s['wrong_order']}{RST}")
    print(f"  {'Empty sections':<30} {(Y if s['empty'] else DIM)}{s['empty']}{RST}")
    print(f"  {'Optional missing':<30} {DIM}{s['optional_missing']}{RST}")
    print(f"  {'Extra headings':<30} {DIM}{s['extra_headings']}{RST}")
    print(f"  {'Content before heading':<30} {(Y if s['content_before_heading'] else DIM)}{s['content_before_heading']}{RST}")

    # ── Section-by-section ────────────────────────────────────────────────────
    print(f"\n{'─'*w}")
    print(f"  {'#':<4} {'SECTION':<28} {'STATUS':<13} {'LAYER':<10} {'MATCHED AS'}")
    print(f"{'─'*w}")

    for r in report["section_results"]:
        sc2    = STATUS_COLOR.get(r["status"], W)
        lc     = LAYER_COLOR.get(r["match_layer"] or "", DIM)
        layer  = r["match_layer"] or "—"
        matched= r["matched_heading"] or "—"
        req    = "" if r["required"] else f"{DIM}(opt){RST}"
        pos    = f" @{r['document_position']}" if r["document_position"] else ""
        print(
            f"  {r['order']:<4} {W}{r['name']:<28}{RST} "
            f"{sc2}{r['status']:<13}{RST} "
            f"{lc}{layer:<10}{RST} "
            f"{DIM}{matched}{pos}{RST} {req}"
        )

    # ── Issues ────────────────────────────────────────────────────────────────
    errors   = [i for i in report["issues"] if i["severity"] == "error"]
    warnings = [i for i in report["issues"] if i["severity"] == "warning"]
    infos    = [i for i in report["issues"] if i["severity"] == "info"]

    if errors or warnings:
        print(f"\n{'─'*w}")
        print(f"  ISSUES")
        print(f"{'─'*w}")
        for issue in errors + warnings + infos:
            c = SEV_COLOR.get(issue["severity"], W)
            tag = issue["severity"].upper()
            print(f"  {c}[{tag}]{RST} {issue['code']}")
            print(f"        {DIM}{issue['message']}{RST}")

    print(f"\n{'═'*w}\n")


# ── Demo mode (no real file) ──────────────────────────────────────────────────

DEMO_TEMPLATE_SECTIONS = [
    {"name": "Abstract",          "order": 1,  "required": True},
    {"name": "Introduction",      "order": 2,  "required": True},
    {"name": "Problem Statement", "order": 3,  "required": True},
    {"name": "Objectives",        "order": 4,  "required": True},
    {"name": "Literature Review", "order": 5,  "required": True},
    {"name": "Methodology",       "order": 6,  "required": True},
    {"name": "System Design",     "order": 7,  "required": True},
    {"name": "Implementation",    "order": 8,  "required": True},
    {"name": "Results",           "order": 9,  "required": True},
    {"name": "Conclusion",        "order": 10, "required": True},
    {"name": "References",        "order": 11, "required": True},
    {"name": "Appendix",          "order": 12, "required": False},
]

# Simulated student doc — missing Results, wrong order for Methodology
DEMO_BLOCKS = [
    {"type": "paragraph", "text": "This report is submitted for FYP.", "index": 0, "metadata": {}},  # content before heading
    {"type": "heading",   "text": "Abstract",           "level": 1, "index": 1, "metadata": {}},
    {"type": "paragraph", "text": "This project aims to automate...", "index": 2, "metadata": {}},
    {"type": "heading",   "text": "Intro",               "level": 1, "index": 3, "metadata": {}},   # synonym match
    {"type": "paragraph", "text": "Background of the problem...",     "index": 4, "metadata": {}},
    {"type": "heading",   "text": "Problem",             "level": 1, "index": 5, "metadata": {}},   # synonym match
    {"type": "paragraph", "text": "The problem is defined as...",     "index": 6, "metadata": {}},
    {"type": "heading",   "text": "Project Aims",        "level": 1, "index": 7, "metadata": {}},   # synonym → Objectives
    {"type": "paragraph", "text": "The aims of this project are...",  "index": 8, "metadata": {}},
    {"type": "heading",   "text": "Lit Review",          "level": 1, "index": 9, "metadata": {}},   # synonym
    {"type": "paragraph", "text": "Various studies have shown...",    "index": 10, "metadata": {}},
    {"type": "heading",   "text": "System Design",       "level": 1, "index": 11, "metadata": {}},  # out of order (before Methodology)
    {"type": "paragraph", "text": "The architecture is...",           "index": 12, "metadata": {}},
    {"type": "heading",   "text": "Methdology",          "level": 1, "index": 13, "metadata": {}},  # typo → fuzzy
    {"type": "paragraph", "text": "We used an agile approach...",     "index": 14, "metadata": {}},
    {"type": "heading",   "text": "Implementation",      "level": 1, "index": 15, "metadata": {}},
    # empty section — no content before next heading
    {"type": "heading",   "text": "Conclusion",          "level": 1, "index": 16, "metadata": {}},  # Results missing
    {"type": "paragraph", "text": "In conclusion...",                 "index": 17, "metadata": {}},
    {"type": "heading",   "text": "References",          "level": 1, "index": 18, "metadata": {}},
    {"type": "paragraph", "text": "[1] Smith et al...",               "index": 19, "metadata": {}},
    {"type": "heading",   "text": "Appendix A",          "level": 1, "index": 20, "metadata": {}},  # extra heading
]


def run_demo():
    from services.structure_checker import check_structure
    print("\n[Running built-in demo with simulated messy student document]")
    report = check_structure(
        blocks            = DEMO_BLOCKS,
        template_sections = DEMO_TEMPLATE_SECTIONS,
        use_semantic      = False,
    )
    print_report(report, filename="(demo)", template_name="FYP Template")

    # Dump JSON
    with open("layer3_output.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"Full JSON saved to: layer3_output.json\n")


def run_on_file(file_path: str, template_id: int):
    from services.document_block_extractor import extract_blocks
    from services.structure_checker import check_structure
    from database import get_db
    import json as _json

    # Load template
    conn = get_db()
    row  = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    conn.close()
    if not row:
        print(f"{R}Template {template_id} not found in database.{RST}")
        sys.exit(1)

    raw_sections = _json.loads(row["required_sections"])
    sections = []
    for i, s in enumerate(raw_sections):
        if isinstance(s, str):
            sections.append({"name": s, "order": i+1, "required": True})
        else:
            sections.append(s)

    # Parse document
    blocks = extract_blocks(file_path)
    print(f"\nParsed {len(blocks)} blocks from {file_path}")

    # Run check
    report = check_structure(blocks, sections, use_semantic=False)
    print_report(report, filename=file_path, template_name=row["name"])

    with open("layer3_output.json", "w") as f:
        _json.dump(report, f, indent=2)
    print(f"Full JSON saved to: layer3_output.json\n")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        run_on_file(sys.argv[1], int(sys.argv[2]))
    else:
        run_demo()