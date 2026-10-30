"""
apply_missing_section_preview.py - run from your backend folder (next to main.py),
AFTER apply_missing_sections.py:

    python apply_missing_section_preview.py

Needs the updated missing_sections.py in the same folder. Adds to main.py:

  1. GET  /api/documents/missing-section-previews/{id}[?suggest=true]
        -> for each missing section: where to draw the faded "Missing" heading
           in the Word preview, plus (with suggest=true) an AI starting draft.
  2. POST /api/documents/insert-missing-section/{id} now accepts an optional
        "content" (the suggested draft) and inserts it instead of the placeholder.
  3. POST /api/documents/apply-content-fix/{id} understands
        fix_type "insert_missing_section", so the existing "Apply Fix" button on
        "Template heading ... was not found" issues works.

Safe to re-run. Saves main.py.bak4. Writes nothing if the result does not compile.
"""
import shutil

PATH = "main.py"
with open(PATH, encoding="utf-8") as fh:
    src = fh.read()
original = src


def replace_once(old, new, label, done_marker):
    global src
    if done_marker in src:
        print(f"[skip]  {label} (already applied)")
        return
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"[FAIL]  {label}: expected 1 match, found {n}. Nothing written.")
    src = src.replace(old, new)
    print(f"[ok]    {label}")


# 1) insert endpoint: pass optional content through
replace_once(
    '''    result = insert_missing_section_by_name(
        working_copy, tmpl.get("required_sections", []), name
    )
''',
    '''    result = insert_missing_section_by_name(
        working_copy,
        tmpl.get("required_sections", []),
        name,
        content=payload.get("content"),
    )
''',
    "insert endpoint accepts suggested content",
    'content=payload.get("content"),',
)

# 2) preview endpoint
PREVIEW_ENDPOINT = '''@app.get("/api/documents/missing-section-previews/{document_id}", tags=["Documents"])
async def missing_section_previews_endpoint(
    document_id: int,
    user_id: int = Query(...),
    suggest: bool = Query(False),
):
    """
    Data for the faded "Missing" headings in the Word preview.
    suggest=true also asks the AI for a short starting draft per missing section
    (sends heading titles + a ~1500 character excerpt; max 6 sections).
    """
    from missing_sections import (
        build_previews,
        build_suggestion_prompt,
        detect_missing_sections,
        document_context,
    )

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    info = detect_missing_sections(working_copy, tmpl.get("required_sections", []))
    previews = build_previews(info) if info.get("reliable") else []

    if suggest and previews:
        context = document_context(working_copy)
        try:
            client = await _get_ai_client()
        except Exception as exc:
            client = None
            print(f"[missing-previews] AI client unavailable: {exc}")

        async def _draft(p):
            if client is None:
                p["suggestion_error"] = "AI is not configured."
                return
            try:
                resp = await client.messages.create(
                    model=ANALYSIS_MODEL,
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": build_suggestion_prompt(p["name"], context),
                    }],
                )
                p["suggested_content"] = "".join(
                    getattr(b, "text", "") or ""
                    for b in (getattr(resp, "content", None) or [])
                ).strip()
            except Exception as exc:
                p["suggestion_error"] = str(exc)[:200]

        await asyncio.gather(*[_draft(p) for p in previews[:6]])

    return {
        "status": "success",
        "document_id": document_id,
        "reliable": bool(info.get("reliable")),
        "reason": info.get("reason", ""),
        "previews": previews,
    }


'''
TOC_ANCHOR = '@app.get("/api/toc-check/{document_id}", tags=["Documents"])\n'
replace_once(
    TOC_ANCHOR,
    PREVIEW_ENDPOINT + TOC_ANCHOR,
    "add missing-section-previews endpoint",
    "def missing_section_previews_endpoint(",
)

# 3) Apply Fix: new fix_type branch in apply_content_fix
BRANCH = '''    elif fix_type == "insert_missing_section":
        from missing_sections import insert_missing_section_by_name

        details = payload.get("fix_details") if isinstance(payload.get("fix_details"), dict) else {}
        section_name = str(
            payload.get("section_name") or details.get("section_name") or ""
        ).strip()
        if not section_name:
            raise HTTPException(status_code=400, detail="section_name is required")
        res = insert_missing_section_by_name(
            working_copy,
            tmpl.get("required_sections", []),
            section_name,
            content=payload.get("content"),
        )
        ok = bool(res.get("inserted"))
        msg = (
            f'Added a "{section_name}" section.'
            if ok
            else res.get("reason", "Section was not added.")
        )
        if ok:
            try:
                apply_template_reformat(
                    working_copy,
                    tmpl["formatting_rules"],
                    tmpl.get("required_sections", []),
                )
            except Exception as exc:
                print(f"[apply-content-fix] reformat skipped (non-fatal): {exc}")
'''
FORMATTING_ANCHOR = '''    elif fix_type == "formatting":
        ok, msg = apply_template_reformat(
'''
replace_once(
    FORMATTING_ANCHOR,
    BRANCH + FORMATTING_ANCHOR,
    "Apply Fix understands insert_missing_section",
    'elif fix_type == "insert_missing_section":',
)

try:
    compile(src, PATH, "exec")
except SyntaxError as exc:
    raise SystemExit(f"[FAIL]  patched file has a syntax error: {exc}. Nothing written.")

if src == original:
    print("\nNo changes needed.")
else:
    shutil.copy(PATH, PATH + ".bak4")
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(src)
    print(f"\nDone. Backup saved as {PATH}.bak4")
