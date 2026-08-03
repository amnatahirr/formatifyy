# Accuracy / e2e production wiring

Confirmed against `main._run_analysis` → `dispatcher.dispatch_all` + corpus plagiarism.

| Feature | Exact production function | File | Accuracy scorer calls |
|---------|---------------------------|------|------------------------|
| grammar | `check_grammar` | `backend/functions/grammar.py` | `production_runners.run_check_grammar` → **REAL LLM** |
| formatting | `check_formatting` | `backend/functions/formatting.py` | `production_runners.run_check_formatting` → **REAL LLM** |
| image_relevance | `analyze_image_relevance_sync` (same core as `check_images_combined`) | `backend/functions/image_relevance.py` | `production_runners.run_image_relevance` → **REAL CLIP** (synthetic PNG) |
| list_detection | `detect_list_groups` | `backend/list_detection.py` | `production_runners.run_list_detection` → **REAL** (deterministic) |
| plagiarism (analyze) | `check_document_against_fyp_corpus` → `detect_plagiarism` | `backend/plagiarism/pipeline.py` / `detector.py` | `production_runners.run_plagiarism_corpus` → **REAL** detector + temp corpus |
| heading / toc | `analyze_headings` + `find_missing_template_headings` | `backend/heading_analysis.py` | `production_runners.run_heading_analysis` → **REAL** (deterministic) |

**Env for LLM features:** `GEMINI_API_KEY` (preferred) or `ANTHROPIC_API_KEY`.

**NOT used anymore:** `naive_grammar_probe`, heading set-diff stand-in, `_extract_keywords` jaccard stand-in, `word_jaccard`-only plagiarism scorer.
