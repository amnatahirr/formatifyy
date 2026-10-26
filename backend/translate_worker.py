import sys, json
import argostranslate.translate as argos

data = json.load(sys.stdin)
target = data["target"]
out = [argos.translate(t, "en", target) for t in data["texts"]]
sys.stdout.write(json.dumps(out, ensure_ascii=False))