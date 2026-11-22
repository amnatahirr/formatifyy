# Image relevance: backend pipeline (terminal only, frontend later)

Copy this folder to `brain/ml/image_rel/`. Run every command from the PROJECT ROOT.
Add `data/` to .gitignore. Install: `pip install numpy pandas scikit-learn xgboost pillow joblib torch transformers sentence-transformers`
(optional: `pytesseract` for --ocr, `anthropic` for stage 6).

Default paths (override with env vars, see config.py): data/parsed, data/images, data/splits.csv.

## Gate 0: plumbing test (no downloads, ~1 min). Must say SMOKE TEST PASSED
    python brain/ml/image_rel/run_smoke_test.py
(The numbers it prints are meaningless; it only proves the code runs.)

## Gate 1: does the code understand YOUR data?
    python brain/ml/image_rel/s0_inspect.py
Need "[OK] images resolved ...". If it says ACTION NEEDED, paste the output to Claude.

## Gate 2: pairs. Needs "(must be 0)" leakage check = 0
    python brain/ml/image_rel/s1_build_pairs.py
Check results/image_rel/build_summary.json: pos/neg counts per split, caption %, what was dropped.

## Gate 3: features (first run downloads CLIP/MiniLM, caches image embeddings)
    python brain/ml/image_rel/s2_features.py --backend real
    # optional extras:  --ocr   --blip   --clip-model google/siglip-base-patch16-224
Need "NaN cells: 0" for every file.

## Gate 4: train (uses train + val only)
    python brain/ml/image_rel/s3_train.py
Writes brain/ml/models/image_rel_v1.joblib, results/image_rel/threshold_table_val.csv

## Gate 5: hand-label gold set (test projects only), then evaluate
    python brain/ml/image_rel/s4_gold_sheet.py --n 300
    # open data/image_rel/gold_sheet.html, fill your_label (1/0/?) in gold_sheet.csv. Do NOT look at model scores.
    python brain/ml/image_rel/s6_claude_baseline.py     # optional, costs API calls -> Claude column
    python brain/ml/image_rel/s5_evaluate.py            # -> results/image_rel/comparison.md

## Gate 6: inference API check (what engine.py will call later)
    python -c "import sys; sys.path.insert(0,'brain/ml/image_rel'); from image_relevance_local import LocalImageRelevance as L; print(L().score('PATH_TO_IMAGE.png','3.1 Login Module','Figure 3.1: Login screen','System Design','section text here'))"

Pass the section text and chapter whenever the app has them: scores are better with that context.
Only after all gates pass do we wire it into engine.py (and then the frontend).
