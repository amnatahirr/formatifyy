"""Re-extract images PROPERLY and write new parsed JSONL with image blocks in reading order.

Why: the old extractor used page.get_images(), which lists every image in the page's
resource dictionary (often the whole document's pool), not what is drawn on the page.
Result: one report's images were saved again on every page, and no image blocks were
written into the JSONL, so the pipeline could not link images to sections.

This script:
  PDF : uses page.get_image_info(xrefs=True) -> only images actually drawn, with bbox.
        Saves each xref once per report. Drops logos/headers repeated on >3 pages and tiny images.
        Inserts an image block into the text blocks after the last block above it on that page.
  DOCX: walks paragraphs in order, saves embedded pictures, inserts the image block after
        the last non-empty paragraph that came before it.
Originals are NOT touched. Output goes to new folders.

Run from project root (PowerShell):
  python brain/ml/image_rel/extract_images.py --raw brain/ml/data/raw --parsed brain/ml/data/parsed `
      --out-parsed brain/ml/data/parsed_img --out-images brain/ml/data/images_clean
Quick test on 5 reports first:  add  --limit 5
"""
import argparse, io, json, sys
from collections import defaultdict
from pathlib import Path

MIN_W, MIN_H, MIN_AREA = 120, 80, 20000
MAX_ASPECT = 8.0
MAX_PAGES_REPEAT = 3          # same xref on more pages than this => logo/header, drop


def read_jsonl(p):
    rows = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def keep_size(w, h):
    if w < MIN_W or h < MIN_H or w * h < MIN_AREA:
        return False
    return max(w / h, h / w) <= MAX_ASPECT


def flatten_save(img_bytes, out_path):
    """Save any image as RGB PNG on white background (avoids black transparent areas)."""
    from PIL import Image
    im = Image.open(io.BytesIO(img_bytes))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    if not keep_size(*im.size):
        return None
    im.save(out_path, "PNG")
    return im.size


def pdf_images(pdf_path, img_dir):
    import fitz
    doc = fitz.open(pdf_path)
    per_page, pages_of = [], defaultdict(set)
    for pno, page in enumerate(doc, start=1):
        try:
            infos = page.get_image_info(xrefs=True)
        except Exception:
            infos = []
        for info in infos:
            xr = info.get("xref", 0)
            if not xr:
                continue
            pages_of[xr].add(pno)
            per_page.append((pno, xr, info["bbox"]))
    saved, out = {}, []
    for pno, xr, bbox in per_page:
        if len(pages_of[xr]) > MAX_PAGES_REPEAT:
            continue
        if xr not in saved:
            try:
                pix = fitz.Pixmap(doc, xr)
                sm = doc.extract_image(xr).get("smask", 0)
                if sm:
                    pix = fitz.Pixmap(pix, fitz.Pixmap(doc, sm))
                if pix.colorspace and pix.colorspace.n > 3:      # CMYK -> RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                data = pix.tobytes("png")
            except Exception:
                saved[xr] = None
                continue
            name = f"x{xr:06d}.png"
            img_dir.mkdir(parents=True, exist_ok=True)
            size = flatten_save(data, img_dir / name)
            saved[xr] = name if size else None
        if saved[xr]:
            out.append({"page": pno, "y0": float(bbox[1]), "x0": float(bbox[0]), "file": saved[xr]})
    return out


def merge_pdf(blocks, imgs, report, folder=None):
    folder = folder or report
    """Insert image blocks after the last text block on the same page with y0 <= image y0."""
    out = list(blocks)
    for im in sorted(imgs, key=lambda d: (d["page"], d["y0"], d["x0"]), reverse=True):
        pos = None
        for i, b in enumerate(out):
            if b.get("page") == im["page"] and isinstance(b.get("y0"), (int, float)) and b["y0"] <= im["y0"] + 2:
                pos = i
        if pos is None:      # no text above on this page: put before the first block of the page
            pos = next((i - 1 for i, b in enumerate(out) if b.get("page") == im["page"]), len(out) - 1)
        out.insert(pos + 1, make_block(report, im["page"], im["y0"], im["x0"], f"{folder}/{im['file']}"))
    return out


def make_block(report, page, y0, x0, rel_path):
    return {"report": report, "page": page, "text": "", "font_size": None, "bold": False, "font": "",
            "x0": x0, "y0": y0, "style": "image", "source": "image", "image_path": rel_path}


def docx_images(docx_path, img_dir):
    import docx
    from PIL import Image  # noqa
    d = docx.Document(docx_path)
    ns_blip = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    ns_embed = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    out, last_text, n, seen = [], "", 0, {}
    for p in d.paragraphs:
        t = p.text.strip()
        for blip in p._element.iter(ns_blip):
            rid = blip.get(ns_embed)
            if not rid or rid not in d.part.related_parts:
                continue
            if rid not in seen:
                img_dir.mkdir(parents=True, exist_ok=True)
                name = f"d{n:04d}.png"
                try:
                    size = flatten_save(d.part.related_parts[rid].blob, img_dir / name)
                except Exception:
                    size = None
                seen[rid] = name if size else None
                n += 1
            if seen[rid]:
                out.append({"after_text": last_text, "file": seen[rid]})
        if t:
            last_text = t
    return out


def merge_docx(blocks, imgs, report, folder=None):
    folder = folder or report
    out = list(blocks)
    cursor = 0
    for im in imgs:
        pos = None
        if im["after_text"]:
            key = im["after_text"][:80]
            for i in range(cursor, len(out)):
                if (out[i].get("text") or "").strip()[:80] == key:
                    pos = i
                    break
        if pos is None:
            pos = cursor if cursor < len(out) else len(out) - 1
        out.insert(pos + 1, make_block(report, None, None, None, f"{folder}/{im['file']}"))
        cursor = pos + 2
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--out-parsed", required=True)
    ap.add_argument("--out-images", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    raw = {}
    for f in Path(a.raw).iterdir():
        if f.suffix.lower() in (".pdf", ".docx"):
            raw[f.stem] = f
    out_p, out_i = Path(a.out_parsed), Path(a.out_images)
    out_p.mkdir(parents=True, exist_ok=True)
    stats = {"reports": 0, "no_raw_match": [], "with_images": 0, "images": 0, "failed": []}
    files = sorted(Path(a.parsed).glob("*.jsonl"))
    if a.limit:
        files = files[:a.limit]
    for jf in files:
        rep = jf.stem
        src = raw.get(rep)
        blocks = read_jsonl(jf)
        if src is None:
            stats["no_raw_match"].append(rep)
            continue
        safe = rep.rstrip(" .")      # Windows strips trailing spaces/dots from folder names
        try:
            if src.suffix.lower() == ".pdf":
                imgs = pdf_images(src, out_i / safe)
                merged = merge_pdf(blocks, imgs, rep, safe)
            else:
                imgs = docx_images(src, out_i / safe)
                merged = merge_docx(blocks, imgs, rep, safe)
        except Exception as e:
            stats["failed"].append(f"{rep}: {e}")
            continue
        for i, b in enumerate(merged):
            b["idx"] = i
        with open(out_p / jf.name, "w", encoding="utf-8") as f:
            for b in merged:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")
        stats["reports"] += 1
        stats["images"] += len(imgs)
        stats["with_images"] += 1 if imgs else 0
        print(f"{rep[:60]:60s} images={len(imgs)}")
    print("\nDONE", {k: (v if not isinstance(v, list) else len(v)) for k, v in stats.items()})
    if stats["no_raw_match"]:
        print("No raw file with same name for:", stats["no_raw_match"][:10])
    if stats["failed"]:
        print("Failed:", stats["failed"][:10])


if __name__ == "__main__":
    sys.exit(main())
