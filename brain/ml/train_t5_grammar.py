"""
train_t5_grammar.py - Grammar Step 7: fine-tune flan-t5-base on "wrong -> correct" pairs (run on a Colab GPU).

In Colab, first run:
    !pip install -q transformers datasets accelerate sentencepiece
Then upload the data files and run:
    !python train_t5_grammar.py --train train_pairs_own.jsonl --val val_pairs_own.jsonl --out t5_grammar_ft

Options:
    --prefix       keep identical to the baseline prompt so the before/after comparison is fair
    --use_jfleg    also add the JFLEG dev set (real human errors, small)
    --c4_n 50000   also add this many pairs from C4_200M (0 = off)
"""
import argparse
import json
import random

import torch
from datasets import Dataset
from transformers import (AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq,
                          Seq2SeqTrainer, Seq2SeqTrainingArguments)


def load_jsonl(p):
    return [json.loads(line) for line in open(p, encoding="utf-8")]


def public_pairs(use_jfleg, c4_n, seed):
    """(src, tgt) pairs from public datasets. Skips a dataset (with a message) if it cannot be loaded."""
    pairs = []
    if use_jfleg:
        try:
            from datasets import load_dataset
            ds = load_dataset("jhu-clsp/jfleg", split="validation")
            for r in ds:
                for ref in r["corrections"]:
                    pairs.append({"src": r["sentence"], "tgt": ref})
            print(f"JFLEG: {len(pairs)} pairs")
        except Exception as e:
            print("Could not load JFLEG, skipping:", e)
    if c4_n:
        try:
            from datasets import load_dataset
            ds = load_dataset("liweili/c4_200m", split="train", streaming=True)
            ds = ds.shuffle(seed=seed, buffer_size=10000)
            n0 = len(pairs)
            for r in ds:
                if 6 <= len(r["input"].split()) <= 60:
                    pairs.append({"src": r["input"], "tgt": r["output"]})
                if len(pairs) - n0 >= c4_n:
                    break
            print(f"C4_200M: {len(pairs) - n0} pairs")
        except Exception as e:
            print("Could not load C4_200M, skipping:", e)
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--out", default="t5_grammar_ft")
    ap.add_argument("--model", default="google/flan-t5-base")
    ap.add_argument("--prefix", default="Fix grammar: ")
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--grad_accum", type=int, default=2)
    ap.add_argument("--max_len", type=int, default=160)
    ap.add_argument("--use_jfleg", action="store_true")
    ap.add_argument("--c4_n", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    random.seed(args.seed)
    own_train = load_jsonl(args.train)
    val = load_jsonl(args.val)
    extra = public_pairs(args.use_jfleg, args.c4_n, args.seed)
    train = own_train + extra
    random.shuffle(train)
    print(f"train: {len(train)} (own {len(own_train)} + public {len(extra)}) | val: {len(val)}")

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)

    def encode(batch):
        enc = tok([args.prefix + s for s in batch["src"]], max_length=args.max_len, truncation=True)
        enc["labels"] = tok(text_target=batch["tgt"], max_length=args.max_len, truncation=True)["input_ids"]
        return enc

    def to_ds(rows):
        ds = Dataset.from_dict({"src": [r["src"] for r in rows], "tgt": [r["tgt"] for r in rows]})
        return ds.map(encode, batched=True, remove_columns=["src", "tgt"])

    tr_ds, va_ds = to_ds(train), to_ds(val)

    # T5 produces NaN in fp16: use bf16 if the GPU supports it, otherwise fp32 (common on a T4)
    use_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    print("precision:", "bf16" if use_bf16 else "fp32 (common on a T4, a bit slower)")

    # warmup_ratio was removed in newer transformers versions, so compute warmup steps ourselves
    steps_per_epoch = max(1, len(tr_ds) // (args.batch * args.grad_accum))
    warmup = max(1, int(0.03 * steps_per_epoch * args.epochs))

    targs = Seq2SeqTrainingArguments(
        output_dir=args.out,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch * 2,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        optim="adafactor",
        num_train_epochs=args.epochs,
        warmup_steps=warmup,
        lr_scheduler_type="linear",
        bf16=use_bf16,
        eval_strategy="steps",
        eval_steps=1000,
        save_strategy="steps",
        save_steps=1000,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=100,
        report_to="none",
        seed=args.seed,
    )
    trainer = Seq2SeqTrainer(model=model, args=targs, train_dataset=tr_ds, eval_dataset=va_ds,
                             data_collator=DataCollatorForSeq2Seq(tok, model=model), processing_class=tok)
    trainer.train()
    # Keep lm_head untied in the saved config so older transformers versions (e.g. on a Mac)
    # load the model correctly instead of producing garbage output.
    model.config.tie_word_embeddings = False
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)

    # Quick sanity check: model output on 8 validation pairs
    model.eval()
    dev = next(model.parameters()).device
    sample = random.sample(val, 8)
    enc = tok([args.prefix + r["src"] for r in sample], return_tensors="pt", padding=True,
              truncation=True, max_length=args.max_len).to(dev)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=args.max_len, num_beams=4)
    for r, o in zip(sample, tok.batch_decode(out, skip_special_tokens=True)):
        print(f"\nSRC  : {r['src']}\nGOLD : {r['tgt']}\nMODEL: {o}")
    print(f"\nModel saved in {args.out}/ (download it or copy it to Drive)")


if __name__ == "__main__":
    main()