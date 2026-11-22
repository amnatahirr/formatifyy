"""
grammar_noise.py  -  saaf sentence mein jaan-boojh kar ghalti daalta hai.

Test set (Step 4) aur training data (Step 6) dono yahi use karenge, taake error ki
qismein ek jaisi hon. Test aur train mein alag 'seed' use hota hai.

corrupt(sentence, rng, n_errors=1) -> (ghalat_sentence, [error_types])  ya  None
"""
import random
import re

VERB_SWAP = {"is": "are", "are": "is", "was": "were", "were": "was", "has": "have",
             "have": "has", "does": "do", "do": "does"}
PREPS = ["in", "on", "at", "of", "to", "for", "with", "from", "by"]


def _words(s):
    return s.split(" ")


def _article_drop(s, rng):
    w = _words(s)
    idx = [i for i, x in enumerate(w) if i > 0 and x.lower() in ("a", "an", "the")]
    if not idx:
        return None
    del w[rng.choice(idx)]
    return " ".join(w)


def _article_wrong(s, rng):
    w = _words(s)
    idx = [i for i, x in enumerate(w) if x.lower() in ("a", "an")]
    if not idx:
        return None
    i = rng.choice(idx)
    new = "an" if w[i].lower() == "a" else "a"
    w[i] = new.capitalize() if w[i][0].isupper() else new
    return " ".join(w)


def _verb_agreement(s, rng):
    w = _words(s)
    idx = [i for i, x in enumerate(w) if x in VERB_SWAP]
    if not idx:
        return None
    i = rng.choice(idx)
    w[i] = VERB_SWAP[w[i]]
    return " ".join(w)


def _comma_drop(s, rng):
    idx = [m.start() for m in re.finditer(r",", s)]
    if not idx:
        return None
    i = rng.choice(idx)
    return s[:i] + s[i + 1:]


def _typo(s, rng):
    w = _words(s)
    idx = [i for i, x in enumerate(w) if x.isalpha() and x.islower() and len(x) >= 5]
    if not idx:
        return None
    i = rng.choice(idx)
    x = w[i]
    kind = rng.choice(["swap", "drop", "double"])
    j = rng.randrange(1, len(x) - 2)
    if kind == "swap" and x[j] != x[j + 1]:
        x = x[:j] + x[j + 1] + x[j] + x[j + 2:]
    elif kind == "drop":
        x = x[:j] + x[j + 1:]
    else:
        x = x[:j] + x[j] + x[j:]
    if x == w[i]:
        return None
    w[i] = x
    return " ".join(w)


def _word_dup(s, rng):
    w = _words(s)
    idx = [i for i, x in enumerate(w) if x.isalpha() and len(x) >= 2]
    if not idx:
        return None
    i = rng.choice(idx)
    return " ".join(w[: i + 1] + [w[i]] + w[i + 1:])


def _prep_swap(s, rng):
    w = _words(s)
    idx = [i for i, x in enumerate(w) if x in PREPS]
    if not idx:
        return None
    i = rng.choice(idx)
    w[i] = rng.choice([p for p in PREPS if p != w[i]])
    return " ".join(w)


def _plural(s, rng):
    w = _words(s)
    idx = [i for i, x in enumerate(w) if x.isalpha() and x.islower() and len(x) >= 5
           and x.endswith("s") and not x.endswith(("ss", "us", "is"))]
    if not idx:
        return None
    i = rng.choice(idx)
    w[i] = w[i][:-1]
    return " ".join(w)


def _case_start(s, rng):
    if len(s) < 2 or not s[0].isupper() or s[:2].isupper():
        return None
    return s[0].lower() + s[1:]


OPS = {
    "article_missing": _article_drop,
    "article_wrong": _article_wrong,
    "verb_agreement": _verb_agreement,
    "comma_missing": _comma_drop,
    "spelling": _typo,
    "repeated_word": _word_dup,
    "preposition": _prep_swap,
    "plural_singular": _plural,
    "capitalization": _case_start,
}


def corrupt(sentence, rng, n_errors=1):
    cur, used = sentence, []
    names = list(OPS)
    rng.shuffle(names)
    for name in names:
        if len(used) == n_errors:
            break
        out = OPS[name](cur, rng)
        if out and out != cur:
            cur = out
            used.append(name)
    if not used or cur == sentence:
        return None
    return cur, used