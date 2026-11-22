"""STAGE 4: make the hand-label sheet from TEST projects only.
Model predictions and auto-labels are NOT shown (avoids anchoring). You fill `your_label`:
  1 = this image belongs in this section,  0 = it does not,  ? = cannot tell (skipped).
Outputs: data/image_rel/gold_sheet.csv (fill this) + gold_sheet.html (view images while labelling).
Run:  python brain/ml/image_rel/s4_gold_sheet.py [--n 300]"""
import argparse, html, random
import pandas as pd
from pathlib import Path
import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    df = pd.read_json(config.WORK_DIR / "pairs_test.jsonl", lines=True, dtype={"caption": str})
    want = {"pos": int(a.n * .5), "hard": int(a.n * .33), "easy": a.n - int(a.n * .5) - int(a.n * .33)}
    parts = [df[df.neg_type == k].sample(min(n, (df.neg_type == k).sum()), random_state=config.SEED) for k, n in want.items()]
    g = pd.concat(parts).sample(frac=1, random_state=config.SEED).reset_index(drop=True)
    g["row"] = g.index + 1
    g["your_label"] = ""
    g[["row", "pair_id", "report", "image_path", "caption", "heading", "chapter", "your_label"]].to_csv(
        config.WORK_DIR / "gold_sheet.csv", index=False)
    cards = []
    for r in g.itertuples():
        cards.append(f"<div style='border:1px solid #ccc;margin:8px;padding:8px;display:flex;gap:12px'>"
                     f"<img src='{Path(r.image_path).resolve().as_uri()}' style='max-width:380px;max-height:260px'>"
                     f"<div><b>#{r.row}</b> &nbsp;<small>{html.escape(r.report)}</small><br>"
                     f"<b>Section:</b> {html.escape(str(r.heading))} <small>({html.escape(str(r.chapter))})</small><br>"
                     f"<b>Caption:</b> {html.escape(str(r.caption or '-'))}<br>"
                     f"<i>Does this image belong in this section? 1 / 0 / ?</i></div></div>")
    (config.WORK_DIR / "gold_sheet.html").write_text("<html><body style='font-family:sans-serif'>" + "".join(cards) + "</body></html>")
    print(f"[OK] {len(g)} rows -> {config.WORK_DIR/'gold_sheet.csv'} ; open gold_sheet.html in a browser, fill `your_label` in the CSV")
    print("     Label from the image + section + caption only. Do not look at model scores.")


if __name__ == "__main__":
    main()
