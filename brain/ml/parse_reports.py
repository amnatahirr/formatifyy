"""
parse_reports.py  -  Step 0 of the FYP report checker.

Folder ke andar ki saari reports (.pdf, .docx, .odt) ko parse karta hai aur har
report ke liye ek JSONL file banata hai:  data/parsed/<report>.jsonl
Har line = ek paragraph/block:
    report, idx, page, text, font_size, bold, font, x0, y0, style, source

Saath mein data/parsed/_index.csv banta hai (har report ki summary) aur
data/parsed/_failed.txt (jo files parse nahi hui).

Install:
    pip install pymupdf python-docx tqdm
    (.odt ke liye LibreOffice 'soffice' install hona chahiye, warna ODT skip hongi)

Run:
    python parse_reports.py --input "path/to/reports_folder" --output data/parsed
    python parse_reports.py --input reports --output data/parsed --images   # images bhi nikaalo
"""
import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document
from tqdm import tqdm

BOLD_FLAG = 16  # PyMuPDF span flag for bold


def parse_pdf(path: Path, img_dir: Path | None):
    rows = []
    doc = fitz.open(path)
    for pno, page in enumerate(doc, start=1):
        data = page.get_text("dict")
        for block in data["blocks"]:
            if block.get("type") != 0:  # 0 = text block
                continue
            texts, sizes, bolds, fonts = [], [], [], []
            for line in block["lines"]:
                line_txt = "".join(s["text"] for s in line["spans"]).strip()
                if not line_txt:
                    continue
                texts.append(line_txt)
                for s in line["spans"]:
                    if not s["text"].strip():
                        continue
                    sizes.append(s["size"])
                    name = s["font"].lower()
                    bolds.append(bool(s["flags"] & BOLD_FLAG) or "bold" in name or "black" in name)
                    fonts.append(s["font"])
            text = " ".join(texts).strip()
            if not text:
                continue
            x0, y0, _, _ = block["bbox"]
            rows.append({
                "page": pno,
                "text": text,
                "font_size": round(max(sizes), 1) if sizes else None,
                "bold": all(bolds) if bolds else False,
                "font": max(set(fonts), key=fonts.count) if fonts else None,
                "x0": round(x0, 1),
                "y0": round(y0, 1),
                "style": None,
            })
        if img_dir is not None:
            for i, img in enumerate(page.get_images(full=True)):
                try:
                    pix = fitz.Pixmap(doc, img[0])
                    if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_dir.mkdir(parents=True, exist_ok=True)
                    pix.save(img_dir / f"p{pno:03d}_{i:02d}.png")
                except Exception:
                    pass
    n_pages = len(doc)
    doc.close()
    return rows, n_pages


def parse_docx(path: Path, img_dir: Path | None):
    rows = []
    doc = Document(path)
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        sizes = [r.font.size.pt for r in p.runs if r.font.size]
        size = max(sizes) if sizes else (p.style.font.size.pt if p.style.font.size else None)
        run_bold = [bool(r.bold) for r in p.runs if r.text.strip()]
        bold = all(run_bold) if run_bold else bool(p.style.font.bold)
        rows.append({
            "page": None,  # DOCX mein page number reliable nahi milta
            "text": text,
            "font_size": size,
            "bold": bold,
            "font": p.runs[0].font.name if p.runs and p.runs[0].font.name else p.style.font.name,
            "x0": None,
            "y0": None,
            "style": p.style.name,  # e.g. "Heading 1" - heading labels ke liye kaafi useful
        })
    if img_dir is not None:
        img_dir.mkdir(parents=True, exist_ok=True)
        for i, rel in enumerate(doc.part.rels.values()):
            if "image" in rel.reltype:
                ext = Path(rel.target_ref).suffix or ".png"
                (img_dir / f"img_{i:03d}{ext}").write_bytes(rel.target_part.blob)
    return rows, None


def odt_to_docx(path: Path, tmp: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", str(tmp), str(path)],
                   check=True, capture_output=True, timeout=180)
    out = tmp / (path.stem + ".docx")
    return out if out.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="reports ka folder (subfolders bhi scan honge)")
    ap.add_argument("--output", default="data/parsed")
    ap.add_argument("--images", action="store_true", help="images data/images/<report>/ mein nikaalo")
    args = ap.parse_args()

    in_dir, out_dir = Path(args.input), Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_root = out_dir.parent / "images" if args.images else None

    exts = {".pdf", ".docx", ".odt"}
    files = sorted(f for f in in_dir.rglob("*") if f.suffix.lower() in exts and not f.name.startswith("~$"))
    print(f"{len(files)} files mili")

    index, failed = [], []
    for f in tqdm(files):
        report_id = f.stem
        img_dir = (img_root / report_id) if img_root else None
        try:
            ext = f.suffix.lower()
            if ext == ".pdf":
                rows, n_pages = parse_pdf(f, img_dir)
            elif ext == ".docx":
                rows, n_pages = parse_docx(f, img_dir)
            else:  # .odt
                with tempfile.TemporaryDirectory() as t:
                    conv = odt_to_docx(f, Path(t))
                    if conv is None:
                        raise RuntimeError("soffice nahi mila ya conversion fail")
                    rows, n_pages = parse_docx(conv, img_dir)

            if not rows:
                raise RuntimeError("koi text nahi mila (scanned PDF? OCR chahiye)")

            with open(out_dir / f"{report_id}.jsonl", "w", encoding="utf-8") as fh:
                for i, r in enumerate(rows):
                    r.update({"report": report_id, "idx": i, "source": str(f)})
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")

            index.append({"report": report_id, "type": ext, "pages": n_pages,
                          "blocks": len(rows), "source": str(f)})
        except Exception as e:
            failed.append(f"{f}  ->  {e}")

    with open(out_dir / "_index.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["report", "type", "pages", "blocks", "source"])
        w.writeheader()
        w.writerows(index)
    (out_dir / "_failed.txt").write_text("\n".join(failed), encoding="utf-8")

    print(f"Parse hui: {len(index)} | Fail: {len(failed)}  (details: {out_dir/'_failed.txt'})")


if __name__ == "__main__":
    main()