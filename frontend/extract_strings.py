import re, glob, json

pat = re.compile(r"""\bTr\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""")
found = set()
for f in glob.glob("lib/**/*.dart", recursive=True):
    src = open(f, encoding="utf-8").read()
    for m in pat.finditer(src):
        s = m.group(1) or m.group(2)
        if s and "$" not in s:
            found.add(s.replace("\\'", "'"))

out = sorted(found)
json.dump(out, open("strings.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "strings")