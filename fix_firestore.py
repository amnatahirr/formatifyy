"""Remove cloud_firestore usage from the Flutter app.
Usage (from the repo root):  python fix_firestore.py frontend/lib
 - deletes import lines for package:cloud_firestore
 - turns `<x> is Timestamp` checks into `false` (the branch can never run
   because dates come from the FastAPI backend as strings)
 - reports any other `Timestamp` mention so you can look at it"""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/lib")
imp = re.compile(r"^[ \t]*import\s+'package:cloud_firestore/[^']*';[ \t]*\r?\n", re.M)
chk = re.compile(r"\b(\w+)\s+is\s+Timestamp\b")


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


changed = 0
for path in root.rglob("*.dart"):
    text = read(path)
    new = imp.sub("", text)
    new = chk.sub("false /* Firestore removed */", new)
    if new != text:
        write(path, new)
        changed += 1
        print(f"patched: {path}")

print(f"\n{changed} file(s) changed.\nRemaining Firestore / Timestamp mentions:")
left = 0
for path in root.rglob("*.dart"):
    for n, line in enumerate(read(path).splitlines(), 1):
        if "cloud_firestore" in line or re.search(r"\bTimestamp\b", line):
            print(f"  {path}:{n}: {line.strip()[:100]}")
            left += 1
if not left:
    print("  none")
