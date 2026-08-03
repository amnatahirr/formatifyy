# Formatify backend — full automated test suite (`tests_full`)

Production-oriented API + pipeline + accuracy/performance suite driven by
[`FUNCTIONAL_TEST_SUMMARY.md`](../../FUNCTIONAL_TEST_SUMMARY.md).

## One-time setup

From `backend/` (use the project venv):

```powershell
.\.venv\Scripts\pip.exe install -r tests_full\requirements-test.txt
.\.venv\Scripts\pytest.exe --version
.\.venv\Scripts\pytest.exe --markers -c tests_full\pytest.ini
```

**Note:** Starlette 0.27’s `TestClient` requires `httpx<0.28`. The requirements
file pins `httpx==0.27.2`.

## How to run

Always pass the suite config (markers, `asyncio_mode`, benchmark defaults).
`pytest.ini` lives under `tests_full/`; its `testpaths = .` is relative to that
directory and `pythonpath = ..` adds `backend/` for imports:

```powershell
cd backend

# Full functional suite (benchmarks disabled by default — fast)
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini

# By priority
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m p0
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m "p0 or p1"

# By module
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m auth
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m fyp
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m vc
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m admin
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m plagiarism
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m pipeline

# Accuracy only (F1 gates)
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m accuracy

# Performance only (enable pytest-benchmark timing output)
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini -m performance --benchmark-enable

# Coverage
.\.venv\Scripts\pytest.exe -c tests_full\pytest.ini --cov=. --cov-report=term-missing
```

### Standalone metric printers

```powershell
cd backend
.\.venv\Scripts\python.exe -m tests_full.metrics.accuracy_report
.\.venv\Scripts\python.exe -m tests_full.metrics.performance_report
```

## Reports

| File | Meaning |
|------|---------|
| `tests_full/metrics/results/accuracy_report.json` | Append-only history of accuracy runs (timestamp, git commit, TP/FP/FN, P/R/F1) |
| `tests_full/metrics/results/performance_report.json` | Append-only history of timing/memory/CPU/throughput |

At the end of a pytest session that collected accuracy/performance rows,
`conftest.py` prints a combined **Accuracy + Performance Summary** table.

### Accuracy thresholds (starter — tune in `metrics/accuracy_report.py`)

| Feature | Min F1 |
|---------|--------|
| list_detection, heading_detection, toc_structure | **0.80** |
| formatting, grammar (heuristic), plagiarism (similarity) | **0.70** |
| default | **0.70** |

Ground-truth fixtures live in `metrics/ground_truth/` as paired `.txt` + `.json`.
Grammar scoring uses a **deterministic heuristic** when LLM keys are absent so CI
stays offline-stable. Raise/lower `THRESHOLDS` when you expand fixtures or wire
live LLM agents.

### Performance policy

- No hard pass/fail on wall-clock (machine-dependent).
- Optional **WARN** (not fail) if a run is **>2× slower** than the previous
  recorded mean for the same test name (`warn_if_regression`).
- Throughput fields: `throughput_pages_per_s`, `throughput_docs_per_min` where applicable.

## Markers

`p0` `p1` `p2` `p3` · `auth` · `fyp` · `vc` · `admin` · `plagiarism` · `pipeline` · `accuracy` · `performance`

## Overlap with existing `backend/test_*.py`

Appendix A of the functional summary lists focused unit tests already in
`backend/` (not under `tests/` — they live as top-level `test_*.py`):

| Existing file | Why not duplicated here |
|---------------|-------------------------|
| `test_heading_and_list_detection.py` | Deep detector unit coverage |
| `test_list_cleanup_safety.py` | Unsafe list skip rules |
| `test_document_lists.py` / `test_toc_pages_and_outline.py` / `test_lof_lot_frontmatter.py` | TOC/LOT/LOF DOCX field behavior |
| `test_table_format_*.py` | Table rule/pipeline internals |
| `test_image_*.py` | Image formatting/relevance |
| `test_frontmatter_detector.py` | Cover/info detection |
| `test_freeform_student_403.py` | Role 403 smoke (also covered via API in `test_documents_core.py`) |
| `test_blank_pages.py` / `test_gemini.py` | Narrow unit concerns |

`tests_full` focuses on **HTTP contracts, auth/roles, multi-tenancy, FYP/VC/admin
flows, and measurable accuracy/performance gates**, and only smoke-touches
pipeline helpers.

## Known limitations

- Ground-truth fixtures are **small/synthetic**; F1 is a regression signal, not
  a research-grade eval.
- Grammar accuracy without API keys is **heuristic** (planted misspellings).
- Performance numbers are **machine-dependent**; compare relative history, not
  absolute SLAs.
- Google Drive OAuth / live SMTP / LibreOffice PDF paths are mostly **mocked or
  status-asserted** (URL-or-400, soft-fail email).
- Fresh SQLite DBs hit a known `init_db` seed-order issue (`templates.org_id`
  before migration). `conftest.py` applies a bootstrap workaround (`# BUG` in
  production `database.py`).
- JWT org resolve currently **does not enforce** `documents_limit` the same way
  `X-Org-Code` lookup does — covered as `xfail` / documented BUG.

## Layout

```
tests_full/
├── conftest.py
├── pytest.ini
├── requirements-test.txt
├── README.md
├── test_*.py
└── metrics/
    ├── accuracy_report.py
    ├── performance_report.py
    ├── ground_truth/
    └── results/
```
