"""STAGE 6 (optional, costs API calls): ask Claude the same question on the gold rows -> 'Claude' column.
Needs: pip install anthropic ; env ANTHROPIC_API_KEY. Never prints the key.
Run:  python brain/ml/image_rel/s6_claude_baseline.py"""
import base64, io, json, os, re, time
import pandas as pd
from PIL import Image
import config

PROMPT = ("A student report has an image under the section heading below.\nSection: {h}\nChapter: {c}\nCaption: {cap}\n"
          "Does this image belong in this section? Answer ONLY JSON: {{\"relevant\": true/false, \"confidence\": 0-1}}")


def main():
    import anthropic
    client = anthropic.Anthropic()
    g = pd.read_csv(config.WORK_DIR / "gold_sheet.csv")
    g = g[g.your_label.astype(str).isin(["0", "1", "0.0", "1.0"])]
    out, cp = [], config.WORK_DIR / "gold_claude.csv"
    done = set(pd.read_csv(cp).pair_id) if cp.exists() else set()
    prev = pd.read_csv(cp).to_dict("records") if cp.exists() else []
    for r in g.itertuples():
        if r.pair_id in done:
            continue
        im = Image.open(r.image_path).convert("RGB")
        im.thumbnail((1024, 1024))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        msg = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=60, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.b64encode(buf.getvalue()).decode()}},
            {"type": "text", "text": PROMPT.format(h=r.heading, c=r.chapter, cap=r.caption if isinstance(r.caption, str) else "-")}]}])
        txt = msg.content[0].text
        m = re.search(r"\{.*\}", txt, re.S)
        try:
            j = json.loads(m.group(0))
            rel, conf = int(bool(j["relevant"])), float(j.get("confidence", 0.5))
        except Exception:
            rel, conf = 0, 0.0
        out.append({"pair_id": r.pair_id, "claude_relevant": rel, "claude_conf": conf})
        pd.DataFrame(prev + out).to_csv(cp, index=False)
        time.sleep(0.3)
    print(f"[OK] {len(prev)+len(out)} Claude answers in {cp}")


if __name__ == "__main__":
    main()
