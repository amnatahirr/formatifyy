"""
compare_headings.py  -  one table: Rules vs XGBoost v1 vs XGBoost v2 on the GOLD set.

  v1 = results/headings/     (before any gold-informed fix)
  v2 = results/headings_v2/  (after one gold-informed fix: 'Unsure' lines trained as Body)

Writes results/headings_comparison.md and prints the same table.

Run (inside brain/ml):
    python3 compare_headings.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = ["H1", "H2", "H3", "Body", "Caption"]

v1 = json.loads((HERE / "results/headings/metrics.json").read_text())["B_gold"]
v2 = json.loads((HERE / "results/headings_v2/metrics.json").read_text())["B_gold"]

rows = [
    ("Rules (baseline)", "-", v1["models"]["Rules"], v1["accuracy_by_sampled_auto_label"], "Rules", None),
    ("XGBoost v1", "before any gold-informed fix", v1["models"]["XGBoost"],
     v1["accuracy_by_sampled_auto_label"], "XGBoost", v1["xgb_with_threshold"]),
    ("XGBoost v2", "after one gold-informed fix", v2["models"]["XGBoost"],
     v2["accuracy_by_sampled_auto_label"], "XGBoost", v2["xgb_with_threshold"]),
]

head = ["Model", "Version", "Accuracy", "Macro-F1 (95% CI)", "Heading-vs-not F1"] + \
       [f"F1 {lab}" for lab in LABELS] + ["Acc on 'Unsure' lines", "% to Claude @0.70", "Acc on confident"]
lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
for name, ver, m, by, key, thr in rows:
    ci = m["macro_f1_95ci"]
    cells = [name, ver, f"{m['accuracy']:.3f}", f"{m['macro_f1']:.3f} ({ci[0]:.3f}-{ci[1]:.3f})",
             f"{m['heading_vs_not_f1']:.3f}"] + [f"{m['per_class'][lab]['f1']:.3f}" for lab in LABELS] + \
            [f"{by['Unsure'][key + '_acc']:.3f}",
             f"{thr['would_go_to_claude_pct']:.1f}%" if thr else "-",
             f"{thr['accuracy_on_confident']:.3f}" if thr else "-"]
    lines.append("| " + " | ".join(cells) + " |")

note = (f"\nGold set: {v1['rows_used']} hand-labelled lines from test projects only (leakage check passed).\n"
        "v2 is 'after one gold-informed fix': the change was chosen after seeing v1's gold errors, "
        "so v2's gold score is slightly optimistic.\n")
text = "# Heading detection: Rules vs XGBoost v1 vs v2 (GOLD set)\n\n" + "\n".join(lines) + "\n" + note
(HERE / "results/headings_comparison.md").write_text(text)
print(text)
