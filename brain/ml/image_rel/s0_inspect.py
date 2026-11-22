"""STAGE 0: check that the pipeline understands your parsed data. Read-only.
Run from project root:  python brain/ml/image_rel/s0_inspect.py"""
import collections, sys
from pathlib import Path
import config
from data_access import *


def find_candidates():
    skip = {"node_modules", ".git", "venv", ".venv", "__pycache__"}
    found = collections.Counter()
    for p in Path(".").rglob("*.jsonl"):
        if not (set(p.parts) & skip):
            found[str(p.parent)] += 1
    return found.most_common(5)


def main():
    files = sorted(config.PARSED_DIR.glob("*.jsonl")) if config.PARSED_DIR.exists() else []
    if not files:
        print(f"[FAIL] No .jsonl in {config.PARSED_DIR}. Folders containing .jsonl files:")
        for d, n in find_candidates():
            print(f"   {d}  ({n} files)  -> set IMGREL_PARSED_DIR to this")
        sys.exit(1)
    print(f"[OK] {len(files)} jsonl files in {config.PARSED_DIR}")
    keys, n_blocks = collections.Counter(), 0
    stats = dict(img_blocks=0, img_no_path=0, img_resolved=0, img_missing_file=0, captions=0,
                 headings=0, sections=0, imgs_with_section=0, reports=0)
    samples, nopath_samples = [], []
    for f in files[:60]:  # sample is enough
        blocks = read_jsonl(f)
        if not blocks:
            continue
        n_blocks += len(blocks)
        stats["reports"] += 1
        for b in blocks:
            keys.update(b.keys())
        report = blocks[0].get("report", f.stem)
        secs, imgs, nopath = parse_report(blocks, report)
        stats["sections"] += len(secs)
        stats["img_no_path"] += nopath
        for im in imgs:
            stats["img_blocks"] += 1
            stats["img_resolved" if im["path"] else "img_missing_file"] += 1
            stats["captions"] += bool(im["caption"])
            stats["imgs_with_section"] += im["sec_id"] is not None
            if len(samples) < 3:
                samples.append((report, im["ref"], bool(im["path"]), im["caption"][:60],
                                secs[im["sec_id"]]["heading"] if im["sec_id"] is not None else None))
        if nopath and len(nopath_samples) < 2:
            nopath_samples += [b for b in blocks if is_image_block(b) and not image_refs(b)][:1]
    print(f"\nKeys seen in blocks ({n_blocks} blocks, first {stats['reports']} reports):")
    for k, v in keys.most_common():
        print(f"   {k:15s} {v}")
    print("\nDetection stats (sampled reports):")
    for k, v in stats.items():
        print(f"   {k:20s} {v}")
    print("\nSample images found (report, ref, file_exists, caption, section):")
    for s in samples:
        print("  ", s)
    ok = stats["img_resolved"] > 0 and stats["sections"] > 0
    print()
    if ok:
        r = stats["img_resolved"] / max(1, stats["img_blocks"])
        print(f"[OK] images resolved to real files: {r:.0%}; with caption: {stats['captions']/max(1,stats['img_resolved']+stats['img_missing_file']):.0%}")
        if r < 0.9:
            print("[WARN] <90% of image refs resolve. Check IMGREL_IMAGES_DIR / path format.")
    else:
        print("[ACTION NEEDED] Could not detect images or sections. Paste this whole output to Claude.")
        if nopath_samples:
            print("Image-like blocks WITHOUT a usable path (first 2):")
            for b in nopath_samples:
                print("  ", {k: (str(v)[:60]) for k, v in b.items()})
        sys.exit(2)


if __name__ == "__main__":
    main()
