import re, glob, json

lit = re.compile(r"""'((?:[^'\\$\n]|\\.){2,90})'""")
ui = re.compile(r"^[A-Z][A-Za-z0-9 ,.'!?()+:&\-–—%]*$")

known = set(json.load(open("assets/lang/hi.json", encoding="utf-8")).keys())
found = set()
for f in glob.glob("lib/**/*.dart", recursive=True):
    for line in open(f, encoding="utf-8"):
        if line.lstrip().startswith(("import", "export", "part")):
            continue
        for m in lit.finditer(line):
            s = m.group(1).replace("\\'", "'")
            if ui.match(s) and s not in known:
                found.add(s)

json.dump(sorted(found), open("new_strings.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(len(found), "new strings")