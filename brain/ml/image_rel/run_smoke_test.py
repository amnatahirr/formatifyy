"""End-to-end SMOKE TEST on synthetic data with the FAKE backend (no downloads, ~1 min).
It proves the plumbing (parsing, splits, dedup, features, training, thresholds, evaluation, inference)
works. Numbers from this test mean NOTHING about CLIP quality. Run:  python run_smoke_test.py"""
import json, os, subprocess, sys, tempfile, random
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
TOPICS = [("Login Module", "login authentication screen"), ("Database Design", "database schema tables"),
          ("Payment Gateway", "payment checkout transaction"), ("Testing Results", "testing results bugs"),
          ("User Interface", "interface dashboard layout"), ("Network Architecture", "network server architecture"),
          ("Report Generation", "report export pdf"), ("Notification Service", "notification alert email")]
FILL = ("This section explains how the system handles requests and stores records for the users of the application "
        "in a reliable way during normal operation. ")


def make(root):
    (root / "parsed").mkdir(parents=True); (root / "images").mkdir()
    rng = random.Random(1)
    reports, seed = [], 0
    dup_img = None
    for r in range(30):
        name = f"CS{r:02d}_Synthetic Project {r}"
        reports.append(name)
        blocks, idx = [], 0

        def add(text, fs=12, bold=False, **kw):
            nonlocal idx
            blocks.append({"report": name, "idx": idx, "page": idx // 5 + 1, "text": text, "font_size": fs,
                           "bold": bold, "font": "TimesNewRoman", "style": kw.pop("style", "Normal"), "source": "docx", **kw})
            idx += 1
        add("Table of Contents", 16, True); add("List of Figures", 16, True)
        add("Chapter 3: System Design", 18, True)
        for k, (topic, words) in enumerate(rng.sample(TOPICS, 6)):
            add(f"3.{k+1} {topic} Design", 14, True)
            add(FILL * 2 + f"The {topic.lower()} component is described here in detail.")
            for j in range(2 if k < 4 else 1):
                seed += 1
                stem = words.replace(" ", "_") + f"_{r}_{j}"
                arr = np.random.default_rng(seed).integers(0, 255, (120, 160, 3), dtype=np.uint8)
                p = root / "images" / f"{stem}.png"
                Image.fromarray(arr).save(p)
                if r == 0 and k == 0 and j == 0:
                    dup_img = arr
                if r == 29 and k == 0 and j == 0 and dup_img is not None:  # duplicate of report 0's image, other split
                    Image.fromarray(dup_img).save(p)
                add("", image_path=f"{stem}.png", style="image")
                add(f"Figure 3.{k+1}.{j+1}: {words.split()[0].title()} {words.split()[1]} of the system")
        # tiny icon (must be filtered) and an image before any heading is not generated here
        Image.fromarray(np.zeros((40, 40, 3), np.uint8)).save(root / "images" / f"icon_{r}.png")
        add("", image_path=f"icon_{r}.png", style="image")
        add("References", 16, True)
        with open(root / "parsed" / f"{name}.jsonl", "w") as f:
            for b in blocks:
                f.write(json.dumps(b) + "\n")
    with open(root / "splits.csv", "w") as f:
        f.write("report,group,split\n")
        for i, n in enumerate(reports):
            f.write(f"{n},g{i},{'train' if i < 20 else 'val' if i < 25 else 'test'}\n")
    # dup image: report 29 is in test, report 0 in train -> duplicate must be dropped from TRAIN


def run(script, env, *args):
    r = subprocess.run([sys.executable, str(HERE / script), *args], env=env, capture_output=True, text=True, cwd=env["IMGREL_ROOT"])
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-2500:]); raise SystemExit(f"FAILED: {script}")
    return r.stdout


def main():
    root = Path(tempfile.mkdtemp(prefix="imgrel_smoke_"))
    make(root)
    env = {**os.environ, "IMGREL_ROOT": str(root), "IMGREL_PARSED_DIR": str(root / "parsed"),
           "IMGREL_IMAGES_DIR": str(root / "images"), "IMGREL_SPLITS_CSV": str(root / "splits.csv"),
           "IMGREL_WORK_DIR": str(root / "work"), "IMGREL_RESULTS_DIR": str(root / "results"),
           "IMGREL_MODEL_PATH": str(root / "model.joblib")}
    print("S0 inspect ...", end=" "); out = run("s0_inspect.py", env); assert "[OK] images resolved" in out; print("ok")
    print("S1 build pairs ...", end=" "); out = run("s1_build_pairs.py", env); assert "must be 0)" in out
    summ = json.load(open(root / "results" / "build_summary.json")); print("ok"); print("   ", summ["drops_and_counts"])
    assert summ["drops_and_counts"].get("drop_too_small_or_banner", 0) == 30, "icons not filtered"
    assert summ["drops_and_counts"].get("drop_dup_other_split", 0) >= 1, "cross-split duplicate not removed"
    assert all(summ["per_split"][s]["pos"] > 0 for s in ("train", "val", "test"))
    print("S2 features (fake) ...", end=" "); out = run("s2_features.py", env, "--backend", "fake"); assert "NaN cells: 0" in out; print("ok")
    print("S3 train ...", end=" "); out = run("s3_train.py", env); print("ok"); print(out[-700:])
    print("S4 gold sheet ...", end=" "); run("s4_gold_sheet.py", env, "--n", "60"); print("ok")
    import pandas as pd
    g = pd.read_csv(root / "work" / "gold_sheet.csv"); g["your_label"] = 1  # fake labelling just to test the code path
    g.to_csv(root / "work" / "gold_sheet.csv", index=False)
    print("S5 evaluate ...", end=" "); out = run("s5_evaluate.py", env); print("ok"); print(out)
    res = pd.read_csv(root / "results" / "test_results.csv")
    auc = res.loc[res.method == "Trained scorer (caption available)", "auc"].iloc[0]
    assert auc > 0.9, f"trained AUC too low on synthetic data: {auc}"
    # inference API
    os.environ.update({k: v for k, v in env.items() if k.startswith("IMGREL")}); sys.path.insert(0, str(HERE))
    from image_relevance_local import LocalImageRelevance
    r = LocalImageRelevance(backend="fake")
    img = str(next((root / "images").glob("login_authentication*.png")))
    a = r.score(img, "3.1 Login Module Design", "Login authentication of the system")
    b = r.score(img, "3.4 Testing Results Design", "Login authentication of the system")
    a2 = r.score(img, "3.1 Login Module Design", "Login authentication of the system", "System Design",
                 "This section explains how the system handles requests and stores records for the login module.")
    b2 = r.score(img, "3.4 Testing Results Design", "Login authentication of the system", "System Design",
                 "This section explains how the system handles requests and stores records for the testing module.")
    print("inference (no section text):", round(a["score"], 3), round(b["score"], 3))
    print("inference (with section text):", round(a2["score"], 3), round(b2["score"], 3), a2)
    assert a["score"] > b["score"] and a2["score"] > b2["score"] and a2["score"] > 0.5
    print(f"\nSMOKE TEST PASSED  (work dir: {root})")


if __name__ == "__main__":
    main()
