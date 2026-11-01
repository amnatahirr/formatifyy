"""Resolve git conflict blocks in a file by keeping the INCOMING side.
Usage:  python take_theirs.py path\to\file
Content outside conflict blocks (auto-merged parts) is left untouched."""
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8", newline="") as fh:
    text = fh.read()

pattern = re.compile(
    r"<<<<<<< [^\r\n]*\r?\n(.*?)=======\r?\n(.*?)>>>>>>> [^\r\n]*\r?\n", re.S)
resolved, n = pattern.subn(lambda m: m.group(2), text)

with open(path, "w", encoding="utf-8", newline="") as fh:
    fh.write(resolved)

left = len(re.findall(r"^(<<<<<<<|=======|>>>>>>>)", resolved, re.M))
print(f"Resolved {n} conflict blocks (kept incoming side) in {path}")
print(f"Conflict markers remaining: {left}")
