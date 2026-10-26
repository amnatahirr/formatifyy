import glob, os, re

for f in glob.glob("lib/**/*.dart", recursive=True):
    src = open(f, encoding="utf-8").read()
    if not re.search(r"\bTr\(", src):
        continue
    if "widgets/tr.dart" in src or f.endswith("widgets/tr.dart"):
        continue
    rel = os.path.relpath("lib/widgets/tr.dart", os.path.dirname(f)).replace(os.sep, "/")
    line = f"import '{rel}';\n"
    imports = list(re.finditer(r"^import .*;\s*$", src, re.M))
    if imports:
        pos = imports[-1].end()
        src = src[:pos] + "\n" + line.rstrip("\n") + src[pos:]
    else:
        src = line + "\n" + src
    open(f, "w", encoding="utf-8").write(src)
    print("import added:", f)