"""Quick verification that _find_title_page_end now returns the correct guard index."""
import glob, sys
sys.path.insert(0, ".")
from docx import Document
from services.heading_detector_v2 import _find_title_page_end

files = sorted(glob.glob("uploads/2026*_sample.docx"))
path = files[-1] if files else "uploads/sample.docx"
print(f"Testing with: {path}\n")

doc = Document(path)
end = _find_title_page_end(doc)
print(f"\ntitle_page_end = {end}")
print(f"Guard: paragraphs 0..{end} will be SKIPPED\n")

FORBIDDEN = [
    "Style Guidelines for Final Year Project ReportsFOR",
    "A project submitted in partial fulfilment of the",
    "COMSATS University Degree",
    "Department of Computer Science",
    "COMSATS University Islamabad, Lahore Campus",
    "Plagiarism Free Certificate",
    "This is to certify that, I am",
]

print("Checking forbidden paragraphs are inside the guard zone:")
all_ok = True
for i, para in enumerate(doc.paragraphs):
    text = para.text.strip()
    for f in FORBIDDEN:
        if f[:40] in text:
            status = "GUARDED (skipped)" if i <= end else "EXPOSED (will be evaluated!)"
            print(f"  [{i:3d}] {status}  -> \"{text[:70]}\"")
            if i > end:
                all_ok = False

print()
print("First 3 paragraphs AFTER the guard (detection starts here):")
count = 0
for i, para in enumerate(doc.paragraphs):
    if i > end and para.text.strip():
        print(f"  [{i:3d}] \"{para.text.strip()[:80]}\"")
        count += 1
        if count == 3:
            break

print()
if all_ok:
    print("RESULT: ALL FORBIDDEN PARAGRAPHS ARE GUARDED - OK")
else:
    print("RESULT: SOME FORBIDDEN PARAGRAPHS ARE EXPOSED - FAIL")
