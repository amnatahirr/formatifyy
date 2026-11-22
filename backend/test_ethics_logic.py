import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import functions.image_ethics as ie

MID = round((ie.HEAD_LOW + ie.HEAD_HIGH) / 2, 2)  # borderline band ke beech

# (p_unsafe, head_class, caption, expected_ethical, expected_engine)
cases = [
    (0.95, "sexual",           "a person standing in a room",             False, "head"),
    (0.90, "weapons_violence", "a diagram of a network",                  False, "head"),
    (0.10, "weapons_violence", "a diagram of a network",                  True,  "head"),
    (0.10, "weapons_violence", "a person injecting drugs into their arm", False, "keyword"),
    (0.10, "weapons_violence", "a swastika symbol painted on a wall",     False, "keyword"),
    (MID,  "weapons_violence", "a table with a bunch of guns and a knife", False, "head+keyword"),
    (MID,  "weapons_violence", "a diagram of a network",                  True,  "head"),
    (MID,  "weapons_violence", "a toy gun lying on a colorful playmat",   True,  "head"),
]

ie.generate_caption_from_b64 = lambda b64, cache_key=None: current["caption"]
current = {}
ok_count = 0
for p, cls, caption, exp_ethical, exp_engine in cases:
    current["caption"] = caption
    ie.predict_unsafe = lambda b64, p=p, cls=cls: {
        "p_unsafe": p, "top_class": cls, "probs": {}}
    r = ie._analyze_local("dummy")
    ok = (r["ethical"] == exp_ethical) and (r["engine"] == exp_engine)
    ok_count += ok
    print(f"[{'OK' if ok else 'FAIL'}] p={p:.2f} | {caption[:42]:42s} -> "
          f"ethical={r['ethical']} engine={r['engine']} category={r['category']}")
print(f"\n{ok_count}/{len(cases)} passed")