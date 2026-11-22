"""
eval_grammar_baselines.py  -  Grammar Step 5: systems ko same test sets par naapna.

Systems (--systems mein comma se likho):
    languagetool                    LanguageTool (offline)
    t5:google/flan-t5-base          bina training wala (zero-shot) T5
    t5:models/grammar_t5/final      tumhara fine-tuned T5 (Step 7 ke baad)
    claude                          purana API engine (ANTHROPIC_API_KEY chahiye)

Run (brain/ml ke andar):
    python3 eval_grammar_baselines.py --systems languagetool --limit 50     # chhota test
    python3 eval_grammar_baselines.py --systems languagetool,t5:google/flan-t5-base
    python3 eval_grammar_baselines.py --systems claude

Output: results/grammar/summary_<system>.json aur preds_<system>.jsonl
"""
import argparse
import csv
import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


# ───────────────────────── systems ─────────────────────────
class LanguageToolSystem:
    name = "languagetool"

    def __init__(self):
        import language_tool_python
        self.tool = language_tool_python.LanguageTool("en-US")

    def correct(self, sents):
        return [self.tool.correct(s) for s in sents]

    def close(self):
        self.tool.close()


class T5System:
    def __init__(self, path):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.torch = torch
        self.name = "t5_" + re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")
        self.dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(path).to(self.dev).eval()

    def correct(self, sents):
        out = []
        for i in range(0, len(sents), 16):
            enc = self.tok(["Fix grammar: " + s for s in sents[i:i + 16]], return_tensors="pt",
                           padding=True, truncation=True, max_length=128).to(self.dev)
            with self.torch.no_grad():
                gen = self.model.generate(**enc, num_beams=4, max_new_tokens=128)
            out += self.tok.batch_decode(gen, skip_special_tokens=True)
        return out

    def close(self):
        pass


class ClaudeSystem:
    name = "claude"
    PROMPT = ("Correct ONLY the grammar, spelling and punctuation errors in the sentence below. "
              "Do not rephrase and do not change the style or wording otherwise. "
              "If the sentence is already correct, return it exactly unchanged. "
              "Return ONLY the sentence, nothing else.\n\nSentence: {s}")

    def __init__(self, model):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self.errors = 0
        self.last_error = ""

    def _one(self, s):
        for attempt in range(3):
            try:
                r = self.client.messages.create(model=self.model, max_tokens=300,
                                                messages=[{"role": "user", "content": self.PROMPT.format(s=s)}])
                return r.content[0].text.strip().strip('"')
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
                if "authentication" in self.last_error.lower() or "401" in self.last_error \
                        or "not_found" in self.last_error.lower() or "404" in self.last_error:
                    break                      # retry ka faida nahi
                time.sleep(2 * (attempt + 1))
        self.errors += 1
        return s                               # API fail -> unchanged

    def correct(self, sents):
        with ThreadPoolExecutor(8) as ex:
            out = list(ex.map(self._one, sents))
        if self.errors:
            print(f"  WARNING: Claude ki {self.errors} calls fail hui. Aakhri error: {self.last_error}", flush=True)
        if self.errors > 0.5 * len(sents):
            raise SystemExit("\nClaude ke zyadatar calls fail ho gaye, isliye natije bekaar hain. "
                             "API key / model ka naam / internet check karo (upar ka error dekho).")
        return out

    def close(self):
        pass


def make_system(spec, claude_model):
    if spec == "languagetool":
        return LanguageToolSystem()
    if spec == "claude":
        return ClaudeSystem(claude_model)
    if spec.startswith("t5:"):
        return T5System(spec[3:])
    raise SystemExit(f"unknown system: {spec}")


# ───────────────────────── evaluation ─────────────────────────
def run(system, sents):
    t0 = time.time()
    out = system.correct(sents)
    return out, (time.time() - t0) / max(len(sents), 1)


def eval_synthetic(system, rows):
    outs, lat = run(system, [r["corrupted"] for r in rows])
    per = defaultdict(lambda: [0, 0, 0, 0])      # n, fixed, changed_wrong, missed
    preds = []
    for r, o in zip(rows, outs):
        if norm(o) == norm(r["original"]):
            k = "fixed"
        elif norm(o) == norm(r["corrupted"]):
            k = "missed"
        else:
            k = "wrong"
        for key in (r["error_type"], "ALL"):
            per[key][0] += 1
            per[key][{"fixed": 1, "wrong": 2, "missed": 3}[k]] += 1
        preds.append({"id": r["id"], "input": r["corrupted"], "gold": r["original"], "output": o, "result": k})
    table = {k: {"n": v[0], "fixed": round(v[1] / v[0], 3), "changed_wrong": round(v[2] / v[0], 3),
                 "missed": round(v[3] / v[0], 3)} for k, v in per.items()}
    return table, preds, lat


def eval_clean(system, rows):
    outs, lat = run(system, [r["text"] for r in rows])
    changed = [(r, o) for r, o in zip(rows, outs) if norm(o) != norm(r["text"])]
    preds = [{"id": r["id"], "input": r["text"], "output": o} for r, o in changed]
    return {"n": len(rows), "false_alarm_rate": round(len(changed) / max(len(rows), 1), 3)}, preds, lat


def eval_manual(system, path):
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8-sig"))
            if r["has_error"].strip().lower() in ("yes", "no")]
    if not rows:
        return None, [], 0
    outs, lat = run(system, [r["text"] for r in rows])
    stats = {"yes": [0, 0, 0], "no": [0, 0]}     # yes: n, exact, changed ; no: n, changed
    preds = []
    for r, o in zip(rows, outs):
        he = r["has_error"].strip().lower()
        if he == "yes":
            stats["yes"][0] += 1
            exact = norm(o) == norm(r["corrected"])
            stats["yes"][1] += exact
            stats["yes"][2] += norm(o) != norm(r["text"])
        else:
            stats["no"][0] += 1
            stats["no"][1] += norm(o) != norm(r["text"])
            exact = norm(o) == norm(r["text"])
        preds.append({"id": r["id"], "input": r["text"], "gold": r["corrected"] if he == "yes" else r["text"],
                      "output": o, "has_error": he, "ok": bool(exact)})
    y, n = stats["yes"], stats["no"]
    return {"with_error_n": y[0], "fixed_exactly": round(y[1] / max(y[0], 1), 3),
            "detected_any_change": round(y[2] / max(y[0], 1), 3),
            "no_error_n": n[0], "false_alarm_rate": round(n[1] / max(n[0], 1), 3)}, preds, lat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="languagetool")
    ap.add_argument("--eval_dir", default="data/grammar/eval")
    ap.add_argument("--manual", default="data/grammar/eval/manual_label_done.csv")
    ap.add_argument("--out", default="results/grammar")
    ap.add_argument("--limit", type=int, default=0, help="synthetic/clean ke liye sirf itne sentences")
    ap.add_argument("--skip_manual", action="store_true")
    ap.add_argument("--claude_model", default="claude-haiku-4-5-20251001")
    args = ap.parse_args()

    ev, out = Path(args.eval_dir), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    syn = load_jsonl(ev / "test_synthetic.jsonl")
    cln = load_jsonl(ev / "test_clean.jsonl")
    if args.limit:
        syn, cln = syn[:args.limit], cln[:args.limit]

    for spec in args.systems.split(","):
        spec = spec.strip()
        print(f"\n=== {spec} ===", flush=True)
        system = make_system(spec, args.claude_model)
        summary = {"system": spec}
        t_syn, p_syn, l1 = eval_synthetic(system, syn)
        t_cln, p_cln, l2 = eval_clean(system, cln)
        summary["synthetic"], summary["clean"] = t_syn, t_cln
        summary["sec_per_sentence"] = round((l1 + l2) / 2, 4)
        if spec == "languagetool":
            summary["note"] = ("clean set LanguageTool se filter hua tha (Step 3), isliye uska false-alarm "
                               "0 hona laazmi hai: is number ko compare mat karna.")
        p_man = []
        if Path(args.manual).exists() and not args.skip_manual:
            summary["manual"], p_man, _ = eval_manual(system, args.manual)
        system.close()

        name = getattr(system, "name", spec)
        json.dump(summary, open(out / f"summary_{name}.json", "w"), indent=2, ensure_ascii=False)
        with open(out / f"preds_{name}.jsonl", "w", encoding="utf-8") as fh:
            for tag, plist in (("synthetic", p_syn), ("clean_changed", p_cln), ("manual", p_man)):
                for p in plist:
                    fh.write(json.dumps({"set": tag, **p}, ensure_ascii=False) + "\n")

        a = t_syn["ALL"]
        print(f"synthetic ({a['n']}): sahi theek {a['fixed']*100:.1f}% | ghalat badla {a['changed_wrong']*100:.1f}% | "
              f"pakda hi nahi {a['missed']*100:.1f}%")
        print(f"clean     ({t_cln['n']}): galat alarm {t_cln['false_alarm_rate']*100:.1f}%"
              + ("  (LanguageTool ke liye ye number ma'ni nahi rakhta)" if spec == "languagetool" else ""))
        if summary.get("manual"):
            m = summary["manual"]
            print(f"manual    : ghalti wale {m['with_error_n']} mein se sahi theek {m['fixed_exactly']*100:.1f}% | "
                  f"theek wale {m['no_error_n']} mein galat alarm {m['false_alarm_rate']*100:.1f}%")
        print(f"speed: {summary['sec_per_sentence']} sec/sentence")
        print("per error type (sahi theek %):",
              {k: round(v['fixed'] * 100) for k, v in t_syn.items() if k != 'ALL'})


if __name__ == "__main__":
    main()