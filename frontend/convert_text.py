import re, glob, shutil

pat = re.compile(r"""\bText\(\s*(?=(?:'(?:[^'\\$]|\\.)*'|"(?:[^"\\$]|\\.)*")\s*[,)])""")
total = 0
for f in glob.glob("lib/**/*.dart", recursive=True):
    src = open(f, encoding="utf-8").read()
    new, n = pat.subn("Tr(", src)
    if n:
        shutil.copy(f, f + ".bak")
        open(f, "w", encoding="utf-8").write(new)
        print(f, n)
        total += n
print("total", total)