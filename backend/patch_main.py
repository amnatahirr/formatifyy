"""
patch_main.py - run from your backend folder (the one containing main.py).

    python patch_main.py                  # fixes the download-formatted crash only
    python patch_main.py --lock-uploads   # + stop serving the whole /uploads folder publicly
    python patch_main.py --jwt            # + require a valid token matching user_id on 5 routes
    python patch_main.py --lock-uploads --jwt

A backup is saved as main.py.bak. Nothing is written if the patched file
fails to compile. Safe to re-run: steps already applied are skipped.
"""
import shutil
import sys

PATH = "main.py"
FLAGS = set(sys.argv[1:])

with open(PATH, encoding="utf-8") as fh:
    src = fh.read()
original = src


def replace_once(old, new, label):
    global src
    n = src.count(old)
    if n == 1:
        src = src.replace(old, new)
        print(f"[ok]    {label}")
        return
    if n == 0 and new in src:
        print(f"[skip]  {label} (already applied)")
        return
    raise SystemExit(
        f"[FAIL]  {label}: expected 1 match, found {n}. "
        "Nothing was written. Edit this one by hand."
    )


def replace_in_function(def_marker, old, new, label):
    """Replace the first `old` that appears after `def_marker`."""
    global src
    i = src.find(def_marker)
    if i == -1:
        raise SystemExit(f"[FAIL]  {label}: function not found. Nothing written.")
    j = src.find(old, i)
    k = src.find(new, i)
    # already patched if `new` appears before the next `old`
    if k != -1 and (j == -1 or k < j) and k - i < 600:
        print(f"[skip]  {label} (already applied)")
        return
    if j == -1 or j - i > 600:
        raise SystemExit(f"[FAIL]  {label}: signature not found. Nothing written.")
    src = src[:j] + new + src[j + len(old):]
    print(f"[ok]    {label}")


# ---------------------------------------------------------------------------
# 1) Always: fix the NameError in download-formatted (stem was mis-indented)
# ---------------------------------------------------------------------------
replace_once(
    '        stem = os.path.splitext(doc["filename"] or "document")[0]\n'
    '    base_name = f"formatted_{stem}"\n\n'
    '    # Decrypt into a temp folder',
    '    stem = os.path.splitext(doc["filename"] or "document")[0]\n'
    '    base_name = f"formatted_{stem}"\n\n'
    '    # Decrypt into a temp folder',
    "download-formatted: fix stem indentation",
)

# ---------------------------------------------------------------------------
# 2) Optional: stop exposing every file under /uploads
# ---------------------------------------------------------------------------
if "--lock-uploads" in FLAGS:
    replace_once(
        'app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")',
        'os.makedirs(os.path.join(UPLOAD_DIR, "images"), exist_ok=True)\n'
        'app.mount(\n'
        '    "/uploads/images",\n'
        '    StaticFiles(directory=os.path.join(UPLOAD_DIR, "images")),\n'
        '    name="uploads-images",\n'
        ')',
        "mount only /uploads/images publicly",
    )

# ---------------------------------------------------------------------------
# 3) Optional: JWT must match the user_id in the URL
# ---------------------------------------------------------------------------
if "--jwt" in FLAGS:
    replace_once(
        "from auth_jwt import create_access_token\n",
        "from auth_jwt import (\n"
        "    create_access_token,\n"
        "    decode_access_token,\n"
        "    bearer_token_from_header,\n"
        ")\n",
        "import decode helpers from auth_jwt",
    )

    verify_fn = '''

def verify_user(request: Request, user_id: int = Query(...)) -> int:
    """Token must be valid AND belong to the user_id in the URL."""
    token = bearer_token_from_header(request.headers.get("authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        token_uid = int(payload.get("user_id", payload.get("sub")))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user_id
'''
    anchor = '        "university_id": row["university_id"],\n    }\n'
    if "def verify_user(" in src:
        print("[skip]  add verify_user (already applied)")
    else:
        replace_once(anchor, anchor + verify_fn, "add verify_user dependency")

    dep = "user_id: int = Depends(verify_user)"
    q = "user_id: int = Query(...)"

    replace_once(
        "def list_documents(user_id: int):",
        f"def list_documents({dep}):",
        "list_documents",
    )
    replace_once(
        f"def download_original_document(document_id: int, {q}):",
        f"def download_original_document(document_id: int, {dep}):",
        "download_original_document",
    )
    replace_in_function(
        "def export_formatted_document(", q, dep, "export_formatted_document"
    )
    replace_in_function(
        "def download_saved_formatted_document(",
        q,
        dep,
        "download_saved_formatted_document",
    )
    replace_in_function(
        "def save_document_draft(", q, dep, "save_document_draft"
    )

# ---------------------------------------------------------------------------
# Compile check, then write
# ---------------------------------------------------------------------------
try:
    compile(src, PATH, "exec")
except SyntaxError as exc:
    raise SystemExit(f"[FAIL]  patched file has a syntax error: {exc}. Nothing written.")

if src == original:
    print("\nNo changes needed.")
else:
    shutil.copy(PATH, PATH + ".bak")
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(src)
    print(f"\nDone. Backup saved as {PATH}.bak")
