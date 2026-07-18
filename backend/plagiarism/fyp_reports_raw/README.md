# Raw FYP Reports (staging)

Drop your **210 previous FYP reports** here as `.docx`, `.pdf`, or `.txt`.

Then run from `backend/`:

```bash
python -m plagiarism.ingest_corpus
```

That extracts plain text into `../fyp_corpus/` for the plagiarism index.

Do not put student upload documents here — this folder is only the reference dataset.
