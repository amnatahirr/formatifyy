"""
benchmark_grammar_speed.py - measure how fast the grammar model runs with different settings on THIS machine,
and how often a faster setting gives the same output as the current (slow) one.

Settings compared:
  - device: cpu vs mps (Apple GPU, if available)
  - beams: 4 (current) vs 1 (greedy, much cheaper)
  - batching: unsorted batches of 8 (current) vs sentences sorted by length in batches of 16
  - int8 dynamic quantization on CPU (smaller/faster weights, small quality risk)

Run (inside brain/ml, .venv active):
    python3 benchmark_grammar_speed.py --model models/t5_grammar_v3 --csv data/grammar/eval/manual_label_done.csv --n 40

Nothing is saved; it only prints a table. "same as reference" = share of sentences where the output is
identical to the reference setting (first row). A high value means the faster setting rarely changes the result.
"""
import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")   # let unsupported MPS ops fall back to CPU

import argparse
import copy
import csv
import time

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

PREFIX = "Fix grammar: "      # same prompt as in training


def load_sentences(path, n):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    return [" ".join(r["text"].split()) for r in rows if r.get("text")][:n]


def run(model, tok, sents, device, beams, batch_size, sort_by_length):
    order = sorted(range(len(sents)), key=lambda i: len(sents[i])) if sort_by_length else list(range(len(sents)))
    outs = [None] * len(sents)
    for i in range(0, len(order), batch_size):
        idx = order[i:i + batch_size]
        enc = tok([PREFIX + sents[j] for j in idx], return_tensors="pt", padding=True,
                  truncation=True, max_length=160).to(device)
        with torch.no_grad():
            gen = model.generate(**enc, num_beams=beams, max_new_tokens=128)
        for j, text in zip(idx, tok.batch_decode(gen, skip_special_tokens=True)):
            outs[j] = " ".join(text.split())
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/t5_grammar_v3")
    ap.add_argument("--csv", default="data/grammar/eval/manual_label_done.csv")
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.model)
    base = AutoModelForSeq2SeqLM.from_pretrained(args.model).eval()
    sents = load_sentences(args.csv, args.n)
    print(f"{len(sents)} sentences | torch {torch.__version__} | CPU threads: {torch.get_num_threads()}")

    # (label, device, model, beams, batch_size, sort_by_length)
    configs = [
        ("cpu  beams=4 batch=8  unsorted (current)", "cpu", base, 4, 8, False),
        ("cpu  beams=4 batch=16 sorted", "cpu", base, 4, 16, True),
        ("cpu  beams=1 batch=16 sorted", "cpu", base, 1, 16, True),
    ]
    if torch.backends.mps.is_available():
        mps_model = copy.deepcopy(base).to("mps")
        configs += [
            ("mps  beams=4 batch=16 sorted", "mps", mps_model, 4, 16, True),
            ("mps  beams=1 batch=16 sorted", "mps", mps_model, 1, 16, True),
        ]
    else:
        print("MPS (Apple GPU) is not available on this machine, skipping it.")
    try:
        quant = torch.quantization.quantize_dynamic(copy.deepcopy(base), {torch.nn.Linear}, dtype=torch.qint8)
        configs += [
            ("cpu  int8 beams=4 batch=16 sorted", "cpu", quant, 4, 16, True),
            ("cpu  int8 beams=1 batch=16 sorted", "cpu", quant, 1, 16, True),
        ]
    except Exception as e:
        print("int8 quantization is not available here, skipping:", e)

    reference = None
    print(f"\n{'setting':<45} {'sec/sentence':>13} {'same as reference':>19}")
    for label, device, model, beams, bs, srt in configs:
        try:
            run(model, tok, sents[:2], device, beams, bs, srt)          # warm-up, not timed
            t0 = time.time()
            outs = run(model, tok, sents, device, beams, bs, srt)
            per = (time.time() - t0) / len(sents)
        except Exception as e:
            print(f"{label:<45} failed: {str(e)[:80]}")
            continue
        if reference is None:
            reference = outs
        same = sum(a == b for a, b in zip(outs, reference)) / len(outs)
        print(f"{label:<45} {per:>12.2f}s {same * 100:>18.0f}%")


if __name__ == "__main__":
    main()