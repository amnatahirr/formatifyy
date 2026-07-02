"""Diagnostic: dump every break-like element in the first 40 paragraphs."""
from docx import Document
from lxml import etree
import glob, os

# Use the most recent upload
files = sorted(glob.glob("uploads/2026*_sample.docx"))
path = files[-1] if files else "uploads/sample.docx"
print(f"Scanning: {path}\n")

doc = Document(path)
ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

for i, para in enumerate(doc.paragraphs):
    if i > 40:
        break
    text = para.text.strip()[:80] if para.text.strip() else "(empty)"
    
    # Check for w:br elements
    breaks = para._element.findall(".//w:br", ns)
    # Check for lastRenderedPageBreak
    lrpb = para._element.findall(".//w:lastRenderedPageBreak", ns)
    # Check for sectPr (section break)
    sect = para._element.findall(".//w:sectPr", ns)
    # Also check pPr for sectPr
    ppr_sect = para._element.findall("w:pPr/w:sectPr", ns)
    
    flags = []
    for br in breaks:
        br_type = br.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type", "(no type attr)")
        flags.append(f"w:br type={br_type}")
    for _ in lrpb:
        flags.append("lastRenderedPageBreak")
    for s in sect + ppr_sect:
        st = s.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type", "")
        flags.append(f"sectPr type={st}")
    
    style = para.style.name if para.style else "None"
    print(f"[{i:3d}] style={style:20s} breaks={flags}  text={text}")

# Also check body-level sectPr between paragraphs
print("\n--- Body-level section breaks ---")
body = doc.element.body
for idx, child in enumerate(body):
    tag = etree.QName(child).localname
    if tag == "sectPr":
        stype = child.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type", "(default)")
        print(f"  body child [{idx}]: sectPr type={stype}")
