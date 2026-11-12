"""
apply_missing_sections.py - the ONE script for missing-section support.
Run from your backend folder (next to main.py):

    python apply_missing_sections.py

Needs missing_sections.py in the same folder. Adds to main.py:
  - GET  /api/documents/missing-sections/{id}        (diagnostic cross-check)
  - POST /api/documents/insert-missing-section/{id}  (adds heading + placeholder)
  - POST /api/documents/suggest-section/{id}         (optional AI outline)
and in the analysis: drops the formatting agent's per-batch 'missing_section'
guesses and makes heading_analysis' real missing sections fixable.

Safe to re-run, and safe if you already ran the older patch_missing_sections.py
and/or patch_missing_sections_v2.py. Saves main.py.bak3. Writes nothing if the
result does not compile.
"""
import shutil

PATH = "main.py"
with open(PATH, encoding="utf-8") as fh:
    src = fh.read()
original = src

ENDPOINTS = '''
# ═══════════════════════════════════════════════════════════════════════════════
# MISSING SECTION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/documents/missing-sections/{document_id}", tags=["Documents"])
def missing_sections_endpoint(document_id: int, user_id: int = Query(...)):
    """Compare the template's required sections with the document's headings."""
    from missing_sections import detect_missing_sections

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    info = detect_missing_sections(working_copy, tmpl.get("required_sections", []))
    return {"status": "success", "document_id": document_id, **info}


@app.post("/api/documents/insert-missing-section/{document_id}", tags=["Documents"])
def insert_missing_section_endpoint(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(...),
):
    """Insert a heading + placeholder for a missing section, in template order."""
    from missing_sections import insert_missing_section_by_name

    name = str(payload.get("section_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="section_name is required")

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    result = insert_missing_section_by_name(
        working_copy, tmpl.get("required_sections", []), name
    )
    if not result.get("inserted"):
        raise HTTPException(status_code=400, detail=result.get("reason", "Not inserted"))

    try:
        apply_template_reformat(
            working_copy,
            tmpl["formatting_rules"],
            tmpl.get("required_sections", []),
        )
    except Exception as exc:
        print(f"[insert-missing-section] reformat skipped (non-fatal): {exc}")

    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": "success",
        "message": f'Added a "{result["section_name"]}" section placeholder.',
        **result,
        **commit,
    }


@app.post("/api/documents/suggest-section/{document_id}", tags=["Documents"])
async def suggest_section_endpoint(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(...),
):
    """Optional: AI outline of what a missing section should contain (sends heading titles only)."""
    from missing_sections import collect_candidate_headings

    name = str(payload.get("section_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="section_name is required")

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    headings = [h["text"] for h in collect_candidate_headings(working_copy)][:60]

    prompt = (
        "A student is writing a university final year project report. "
        f'The report is missing its "{name}" section.\\n'
        "Existing headings in the report:\\n- " + "\\n- ".join(headings) + "\\n\\n"
        f'Give a short outline (4-6 plain bullet points) of what the "{name}" '
        "section should cover for this report. No preamble."
    )
    try:
        client = await _get_ai_client()
        resp = await client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") or "" for b in (getattr(resp, "content", None) or [])
        ).strip()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI suggestion unavailable: {exc}")
    return {"status": "success", "section_name": name, "suggestion": text}


'''

# --- text from the first patch, so it can be removed cleanly ----------------
OLD_BLOCK = '''    # Whole-document missing-section check (replaces per-batch LLM guesses)
    missing_sections_info: Dict[str, Any] = {"reliable": False, "found": [], "missing": []}
    if tmpl and file_path.endswith(".docx"):
        try:
            from missing_sections import detect_missing_sections, missing_sections_to_issues

            missing_sections_info = detect_missing_sections(
                file_path, tmpl.get("required_sections", [])
            )
            if missing_sections_info.get("reliable"):
                ms_issues = missing_sections_to_issues(missing_sections_info["missing"])
                normalized_issues = [
                    i for i in normalized_issues
                    if (i.get("type") or "").lower() != "missing_section"
                ]
                style_issues = [
                    i for i in style_issues
                    if (i.get("type") or "").lower() != "missing_section"
                ]
                normalized_issues.extend(ms_issues)
                style_issues.extend(ms_issues)
        except Exception as exc:
            print(f"[analyze] missing-section check error (non-fatal): {exc}")

'''
OLD_RET = '        "missing_sections": missing_sections_info,\n'

COUNTS = (
    '    major_count = len([i for i in normalized_issues if (i.get("severity") or "").lower() == "major"])\n'
    '    minor_count = len([i for i in normalized_issues if (i.get("severity") or "").lower() == "minor"])\n'
    '    critical_count = len([i for i in normalized_issues if (i.get("severity") or "").upper() == "CRITICAL"])\n'
)

NEW_BLOCK = '''    # Missing sections come from heading_analysis (whole document), added further
    # down. Drop the formatting agent's per-batch guesses: it only sees 4 pages.
    normalized_issues = [
        i for i in normalized_issues if (i.get("type") or "").lower() != "missing_section"
    ]
    style_issues = [
        i for i in style_issues if (i.get("type") or "").lower() != "missing_section"
    ]

'''
NEW_MARKER = "# Missing sections come from heading_analysis (whole document)"

HEAD_OLD = '''                normalized_heading_issues = normalize_issues(heading_issues, image_paths)
                style_issues.extend(normalized_heading_issues)
                normalized_issues.extend(normalized_heading_issues)
'''
HEAD_NEW = '''                normalized_heading_issues = normalize_issues(heading_issues, image_paths)
                for _it in normalized_heading_issues:
                    if (_it.get("type") or "").lower() != "missing_section":
                        continue
                    _name = str(_it.get("matched_template_heading") or "").strip()
                    if not _name:
                        _m = re.search(
                            r'"([^"]+)"',
                            str(_it.get("suggestion") or _it.get("reason") or ""),
                        )
                        _name = _m.group(1).strip() if _m else ""
                    if _name:
                        _it["fix_type"] = "insert_missing_section"
                        _it["fix_details"] = {
                            "section_name": _name,
                            "level": _it.get("heading_level") or 1,
                        }
                style_issues.extend(normalized_heading_issues)
                normalized_issues.extend(normalized_heading_issues)
'''
HEAD_MARKER = '_it["fix_type"] = "insert_missing_section"'


def must_have_once(text, label):
    n = src.count(text)
    if n != 1:
        raise SystemExit(f"[FAIL]  {label}: expected 1 match, found {n}. Nothing written.")


# 0) the three missing-section endpoints
TOC_ANCHOR = '@app.get("/api/toc-check/{document_id}", tags=["Documents"])\n'
if "def missing_sections_endpoint(" in src:
    print("[skip]  missing-section endpoints (already applied)")
else:
    must_have_once(TOC_ANCHOR, "toc-check anchor")
    src = src.replace(TOC_ANCHOR, ENDPOINTS + TOC_ANCHOR)
    print("[ok]    added 3 missing-section endpoints")

# 1+2) analysis pre-filter (replace the old block if present)
if NEW_MARKER in src:
    print("[skip]  pre-filter of LLM missing_section guesses (already applied)")
elif OLD_BLOCK in src:
    src = src.replace(OLD_BLOCK, NEW_BLOCK)
    print("[ok]    replaced first patch's analysis block with the pre-filter")
else:
    must_have_once(COUNTS, "analysis counts anchor")
    src = src.replace(COUNTS, NEW_BLOCK + COUNTS)
    print("[ok]    added pre-filter of LLM missing_section guesses")

# the first patch's response key referenced a variable that no longer exists
if OLD_RET in src:
    src = src.replace(OLD_RET, "")
    print("[ok]    removed old 'missing_sections' response key")

# 3) make heading_analysis' missing sections fixable
if HEAD_MARKER in src:
    print("[skip]  fix info on missing-section issues (already applied)")
else:
    must_have_once(HEAD_OLD, "heading issues anchor")
    src = src.replace(HEAD_OLD, HEAD_NEW)
    print("[ok]    missing-section issues now carry fix_type/fix_details")

try:
    compile(src, PATH, "exec")
except SyntaxError as exc:
    raise SystemExit(f"[FAIL]  patched file has a syntax error: {exc}. Nothing written.")

if src == original:
    print("\nNo changes needed.")
else:
    shutil.copy(PATH, PATH + ".bak3")
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(src)
    print(f"\nDone. Backup saved as {PATH}.bak3")
