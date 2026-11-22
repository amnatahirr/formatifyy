"""Reads parsed-report JSONL, finds images, headings, captions, sections.
ASSUMPTION (verify with s0_inspect.py): each JSONL line is one block with keys like
report, idx, page, text, font_size, bold, style ... and image blocks carry an image path
under one of IMG_KEYS (or style/type == image). Adjust here if your schema differs."""
import json, re, statistics
from pathlib import Path
import config

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
IMG_KEYS = ("image_path", "image", "img_path", "img", "path", "file", "filename", "images", "image_paths")
KIND_KEYS = ("type", "kind", "block_type", "style")
CAP_RE = re.compile(r"^\s*(figure|fig\.?)\s*(\d+(?:[.\-]\d+)*)\s*[:.\-–—]?\s*(.*)$", re.I)
NUM_HEAD_RE = re.compile(r"^\s*(\d+(?:\.\d+){0,3})[.)]?\s+(\S.*)$")
CHAPTER_RE = re.compile(r"^\s*chapter\s+(\d+|[ivx]+)\b[\s:.\-–—]*(.*)$", re.I)
STYLE_HEAD_RE = re.compile(r"heading\s*([1-4])", re.I)
SKIP_HEADINGS = {"list of figures", "list of tables", "table of contents", "contents", "references",
                 "bibliography", "abstract", "acknowledgement", "acknowledgements", "declaration",
                 "list of abbreviations", "appendix", "figures", "tables", "dedication"}
STOP = set("the a an of and or to in for on with by is are be as at from this that it its".split())


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def tokens(s):
    return {t for t in norm(s).split() if len(t) > 2 and t not in STOP}


def jaccard(a, b):
    a, b = tokens(a), tokens(b)
    return len(a & b) / len(a | b) if a and b else 0.0


def image_refs(b):
    """Return list of raw image path strings in a block (may be empty)."""
    refs = []
    kind = " ".join(str(b.get(k, "")).lower() for k in KIND_KEYS)
    for k in IMG_KEYS:
        v = b.get(k)
        vals = v if isinstance(v, list) else [v]
        for x in vals:
            if isinstance(x, str) and Path(x).suffix.lower() in IMG_EXT:
                refs.append(x)
    if not refs and any(w in kind for w in ("image", "picture")):
        return []  # image block without a usable path -> counted as missing by caller
    return refs


def is_image_block(b):
    kind = " ".join(str(b.get(k, "")).lower() for k in KIND_KEYS)
    return bool(image_refs(b)) or any(w in kind for w in ("image", "picture"))


def resolve_image(ref, report):
    cands = [Path(ref), config.IMAGES_DIR / ref, config.IMAGES_DIR / Path(ref).name,
             config.IMAGES_DIR / report / Path(ref).name]
    for c in cands:
        if c.exists() and c.is_file():
            return c
    return None


def _median_font(blocks):
    sizes = [b.get("font_size") for b in blocks
             if isinstance(b.get("font_size"), (int, float)) and len((b.get("text") or "").split()) > 15]
    return statistics.median(sizes) if sizes else None


def heading_level(b, med_font):
    """Return heading level 1-4 or None. Approximate rules; label noise is possible."""
    t = (b.get("text") or "").strip()
    words = t.split()
    if not t or len(words) > 14 or len(t) > 120 or CAP_RE.match(t) or t.lower().startswith("table "):
        return None
    sm = STYLE_HEAD_RE.search(str(b.get("style", "")))
    if sm:
        return int(sm.group(1))
    bold = bool(b.get("bold"))
    fs = b.get("font_size")
    big = isinstance(fs, (int, float)) and med_font and fs >= med_font + 0.5
    emphasised = bold or big
    cm = CHAPTER_RE.match(t)
    if cm and emphasised:
        return 1
    nm = NUM_HEAD_RE.match(t)
    if nm and emphasised and not t.endswith((".", ":", ",")) and len(words) <= 12:
        rest = nm.group(2)
        if rest[:1].isupper() and sum(c.isalpha() for c in rest) >= 3:
            return min(len(nm.group(1).split(".")), 4)
    return None


def parse_report(blocks, report):
    """-> (sections, images). Sections: dicts(sec_id, heading, chapter, level, text, skip).
    Images: dicts(ref, path, sec_id, caption)."""
    med = _median_font(blocks)
    sections, images = [], []
    cur, chapter = None, ""
    n_missing_path = 0
    for pos, b in enumerate(blocks):
        t = (b.get("text") or "").strip()
        if is_image_block(b):
            refs = image_refs(b)
            if not refs:
                n_missing_path += 1
                continue
            cap = _find_caption(blocks, pos)
            for ref in refs:
                images.append({"ref": ref, "path": resolve_image(ref, report),
                               "sec_id": cur["sec_id"] if cur else None, "caption": cap})
            continue
        lvl = heading_level(b, med)
        if lvl:
            if lvl == 1:
                chapter = CHAPTER_RE.sub(lambda m: m.group(2) or t, t) if CHAPTER_RE.match(t) else t
            cur = {"sec_id": len(sections), "heading": t, "chapter": chapter, "level": lvl,
                   "text": "", "skip": norm(re.sub(r"^\d+(\.\d+)*[.)]?\s*", "", t)) in SKIP_HEADINGS
                   or norm(t) in SKIP_HEADINGS}
            sections.append(cur)
        elif cur is not None and len(t.split()) >= 8 and not CAP_RE.match(t):
            if len(cur["text"].split()) < config.SECTION_WORDS:
                cur["text"] = (cur["text"] + " " + t).strip()
    for s in sections:
        s["text"] = " ".join(s["text"].split()[:config.SECTION_WORDS])
    return sections, images, n_missing_path


def _find_caption(blocks, pos):
    own = (blocks[pos].get("text") or "").strip()
    order = [pos] + list(range(pos + 1, min(pos + 4, len(blocks)))) + [pos - 1, pos - 2]
    for j in order:
        if j < 0 or j >= len(blocks):
            continue
        t = (blocks[j].get("text") or "").strip() if j != pos else own
        m = CAP_RE.match(t) if t else None
        if m and not is_image_block(blocks[j]) or (m and j == pos):
            cap = (m.group(3) or "").strip()
            return cap if cap else t
    return ""
