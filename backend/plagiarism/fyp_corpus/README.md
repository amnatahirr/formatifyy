# FYP Reference Corpus

Place **previous university FYP reports** here for local plagiarism checking.

## Recommended layout

```
backend/plagiarism/
├── fyp_reports_raw/     ← put your 210 original reports here (DOCX / PDF / TXT)
├── fyp_corpus/          ← indexed plain-text copies used at runtime (this folder)
└── cache/               ← auto-generated MinHash + FAISS indexes (do not edit)
```

## Quick start

1. Copy your 210 FYP reports into:

   `backend/plagiarism/fyp_reports_raw/`

2. From the `backend/` directory, convert them into this corpus folder:

   ```bash
   python -m plagiarism.ingest_corpus
   ```

3. Ensure `backend/.env` contains:

   ```env
   PLAGIARISM_CORPUS_DIR=plagiarism/fyp_corpus
   PLAGIARISM_INDEX_DIR=plagiarism/cache
   ```

4. Restart the backend. The first analysis rebuilds the index (can take several minutes for ~210 reports); later runs use the cache.

## Supported input formats

| Folder | Formats |
|--------|---------|
| `fyp_reports_raw/` | `.docx`, `.pdf`, `.txt` |
| `fyp_corpus/` (this folder) | `.txt` preferred; `.docx` / `.pdf` also accepted |

You may also drop `.txt` files directly into this folder and skip the ingest script.
