"""
Google Drive OAuth + file list/import routes.

Auth (used by AuthProvider.connectGoogleDrive):
  GET  /api/auth/google/authorize?link_to_user_id=
  GET  /api/auth/google/callback
  GET  /api/auth/google/status
  GET  /api/auth/google/debug/tokens?user_id=

Uploads (used by New Report / DocumentProvider):
  GET  /api/uploads/google-drive/files?user_id=
  POST /api/uploads/google-drive/import?...
  POST /api/uploads/download-from-google-drive?...
  POST /api/uploads/google-drive/auth/init?user_id=
  GET  /api/auth/google/drive-picker?user_id=
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from auth_jwt import create_access_token
from config import settings
from database import get_db
from middleware.org_middleware import resolve_org_id_for_user_action
from services.google_drive_service import GoogleDriveService, _GOOGLE_EXPORT
from template_logic.templates import get_template_by_id

try:
    from googleapiclient.errors import HttpError as GoogleHttpError
except ImportError:  # pragma: no cover
    GoogleHttpError = Exception  # type: ignore

auth_router = APIRouter(prefix="/api/auth", tags=["Auth", "Google Drive"])
uploads_router = APIRouter(prefix="/api/uploads", tags=["Uploads", "Google Drive"])

# In-memory OAuth session store (dev). Survives within one uvicorn process.
oauth_sessions: Dict[str, Dict[str, Any]] = {}

_SUPPORTED_BINARY_EXTS = {".pdf", ".docx", ".doc", ".txt"}
_GOOGLE_DOC_MIME = "application/vnd.google-apps.document"


def _client_id() -> str:
    return settings.GOOGLE_DRIVE_CLIENT_ID or settings.GOOGLE_CLIENT_ID


def _client_secret() -> str:
    return settings.GOOGLE_DRIVE_CLIENT_SECRET or settings.GOOGLE_CLIENT_SECRET


def _upload_dir() -> str:
    return settings.UPLOAD_FOLDER or "uploads"


def _ensure_user(user_id: int):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _store_tokens(user_id: int, access_token: str, refresh_token: Optional[str], expires_in) -> None:
    expiry_iso = None
    try:
        if expires_in is not None:
            seconds = int(expires_in)
            expiry_iso = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
    except (TypeError, ValueError):
        expiry_iso = None

    conn = get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO google_drive_tokens
        (user_id, access_token, refresh_token, token_expiry, created_at, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (user_id, access_token, refresh_token, expiry_iso),
    )
    conn.commit()
    conn.close()


def _save_drive_file_as_document(
    *,
    request: Request,
    user_id: int,
    template_id: int,
    file_id: str,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    org_id = resolve_org_id_for_user_action(request, user_id)
    tmpl = get_template_by_id(template_id, org_id=org_id)
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found for this organization.")

    _ensure_user(user_id)
    service = GoogleDriveService(user_id)
    if not service.initialize_service():
        raise HTTPException(
            status_code=401,
            detail="Google Drive not authorized. Please connect Google Drive first.",
        )

    meta = service.get_file_metadata(file_id)
    drive_name = filename or meta.get("name") or f"gdrive_{file_id}"
    mime = meta.get("mimeType") or ""

    # Normalize export filename for Google Docs → .docx
    display_name = drive_name
    is_workspace = mime.startswith("application/vnd.google-apps.") and mime not in {
        "application/vnd.google-apps.folder",
        "application/vnd.google-apps.shortcut",
    }
    if mime == _GOOGLE_DOC_MIME or (
        is_workspace and mime not in _GOOGLE_EXPORT
    ):
        # Docs Editors files must be exported; force a .docx name for Formatify.
        if not display_name.lower().endswith(".docx"):
            display_name = f"{os.path.splitext(display_name)[0]}.docx"
    elif mime in _GOOGLE_EXPORT:
        _, ext = _GOOGLE_EXPORT[mime]
        if not display_name.lower().endswith(ext):
            display_name = f"{os.path.splitext(display_name)[0]}{ext}"

    ext = os.path.splitext(display_name)[1].lower()
    if not is_workspace and mime not in _GOOGLE_EXPORT and ext not in _SUPPORTED_BINARY_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, DOC, TXT, or Google Docs are supported.",
        )
    if mime in {
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
    }:
        raise HTTPException(
            status_code=400,
            detail="Sheets and Slides are not supported. Open as Google Doc or upload a PDF/DOCX.",
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{display_name}".replace("/", "_").replace("\\", "_")
    file_path = os.path.join(_upload_dir(), safe_name)

    try:
        if not service.download_file(file_id, file_path):
            raise HTTPException(
                status_code=500, detail="Failed to download file from Google Drive"
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GoogleHttpError as exc:
        status = int(getattr(getattr(exc, "resp", None), "status", 500) or 500)
        detail = "Failed to download file from Google Drive"
        try:
            body = getattr(exc, "content", b"") or b""
            text = body.decode("utf-8", errors="ignore") if isinstance(body, (bytes, bytearray)) else str(body)
            if "fileNotDownloadable" in text or "Use Export" in text:
                detail = (
                    "This Google Drive file cannot be downloaded as binary. "
                    "If it is a Google Doc, try again; otherwise export it as DOCX/PDF in Drive first."
                )
            elif "insufficientPermissions" in text or status == 403:
                detail = "Google Drive permission denied for this file."
            elif status == 404:
                detail = "File not found on Google Drive."
        except Exception:
            pass
        raise HTTPException(status_code=400 if status in (400, 403, 404) else 500, detail=detail) from exc

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO documents (user_id, template_id, filename, file_path, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, template_id, display_name, file_path, "pending"),
    )
    document_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO file_sync_status
        (document_id, user_id, source, sync_status, google_drive_id, last_synced, created_at)
        VALUES (?, ?, 'google_drive', 'synced', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (document_id, user_id, file_id),
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "document_id": document_id,
        "filename": display_name,
        "file_path": file_path,
        "source": "google_drive",
        "google_drive_id": file_id,
        "status": "pending",
    }


# ── Auth: connect Google Drive to existing user ──────────────────────────────


@auth_router.get("/google/authorize")
async def google_authorize(link_to_user_id: Optional[int] = Query(None)):
    client_id = _client_id()
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID in .env.",
        )

    session_id = str(uuid.uuid4())
    oauth_sessions[session_id] = {
        "provider": "google",
        "status": "pending",
        "link_to_user_id": link_to_user_id,
    }

    redirect_uri = f"{settings.API_URL.rstrip('/')}/api/auth/google/callback"
    encoded_redirect = quote(redirect_uri, safe="")
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        "response_type=code&"
        f"redirect_uri={encoded_redirect}&"
        "scope=openid%20email%20profile%20https://www.googleapis.com/auth/drive&"
        "access_type=offline&"
        "prompt=consent&"
        f"state={session_id}"
    )
    return auth_url


@auth_router.get("/google/callback")
async def google_callback(code: str = Query(...), state: str = Query(...)):
    try:
        client_id = _client_id()
        client_secret = _client_secret()
        if not client_id or not client_secret:
            raise HTTPException(status_code=400, detail="Google OAuth not configured")

        session_data = oauth_sessions.get(state, {})
        link_to_user_id = session_data.get("link_to_user_id")

        redirect_uri = f"{settings.API_URL.rstrip('/')}/api/auth/google/callback"
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        if token_response.status_code != 200:
            raise Exception(f"Token exchange failed: {token_response.text}")

        tokens = token_response.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise Exception("No access_token in Google response")

        userinfo = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if userinfo.status_code != 200:
            raise Exception("Failed to get Google user info")
        info = userinfo.json()
        google_email = info.get("email") or ""
        google_username = info.get("name") or (google_email.split("@")[0] if google_email else "google_user")

        conn = get_db()
        cursor = conn.cursor()

        if link_to_user_id:
            user = cursor.execute(
                "SELECT id, username, email, role, org_id FROM users WHERE id = ?",
                (link_to_user_id,),
            ).fetchone()
            if not user:
                conn.close()
                raise HTTPException(status_code=404, detail="User to link not found")
            user_id = int(user["id"])
            username = user["username"]
            email = user["email"]
            role = user["role"] or "student"
            org_id = int(user["org_id"]) if user["org_id"] is not None else 1
        else:
            user = cursor.execute(
                "SELECT id, username, email, role, org_id FROM users WHERE email = ?",
                (google_email,),
            ).fetchone()
            if not user:
                from database import hash_password

                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, university_id, role, org_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        google_username,
                        google_email,
                        hash_password("oauth_user"),
                        1,
                        "student",
                        1,
                    ),
                )
                conn.commit()
                user_id = int(cursor.lastrowid)
                username = google_username
                email = google_email
                role = "student"
                org_id = 1
            else:
                user_id = int(user["id"])
                username = user["username"]
                email = user["email"]
                role = user["role"] or "student"
                org_id = int(user["org_id"]) if user["org_id"] is not None else 1

        conn.close()

        _store_tokens(
            user_id,
            access_token,
            tokens.get("refresh_token"),
            tokens.get("expires_in"),
        )

        jwt_token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role=role,
            email=email or google_email,
        )

        if state in oauth_sessions:
            oauth_sessions[state] = {
                "provider": "google",
                "status": "authenticated",
                "id": user_id,
                "username": username,
                "email": email,
                "role": role,
                "token": jwt_token,
                "has_google_drive": True,
                "google_email": google_email,
            }

        title = "Google Drive connected successfully!" if link_to_user_id else "Sign In Successful"
        html = f"""
        <html><head><title>Formatify</title></head>
        <body style="font-family:Arial,sans-serif;text-align:center;padding:50px;background:#1a1a2e;color:#fff;">
          <h1 style="color:#4ade80;">&#10003; {title}</h1>
          <p>Google Account: {google_email}</p>
          <p>You can return to the Formatify app and close this window.</p>
        </body></html>
        """
        return HTMLResponse(content=html)
    except Exception as e:
        html = f"""
        <html><head><title>Formatify - Failed</title></head>
        <body style="font-family:Arial,sans-serif;text-align:center;padding:50px;background:#1a1a2e;color:#fff;">
          <h1 style="color:#ef4444;">&#10007; Connection Failed</h1>
          <p>Error: {str(e)}</p>
          <p>Please try again in the app.</p>
        </body></html>
        """
        return HTMLResponse(content=html, status_code=400)


@auth_router.get("/google/status")
async def google_status():
    for session_id, session_data in list(oauth_sessions.items()):
        if session_data.get("provider") == "google" and session_data.get("status") == "authenticated":
            session = oauth_sessions.pop(session_id)
            return {
                "authenticated": True,
                "id": session.get("id"),
                "username": session.get("username"),
                "email": session.get("email"),
                "role": session.get("role"),
                "token": session.get("token"),
                "has_google_drive": session.get("has_google_drive", False),
                "google_email": session.get("google_email"),
            }
    return {"authenticated": False}


@auth_router.get("/google/debug/tokens")
async def google_debug_tokens(user_id: int = Query(...)):
    conn = get_db()
    user = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return {"error": "User not found", "user_id": user_id, "tokens_found": False}

    token = conn.execute(
        """
        SELECT access_token, refresh_token, token_expiry, created_at, updated_at
        FROM google_drive_tokens WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    if not token:
        return {
            "user_id": user_id,
            "email": user["email"],
            "tokens_found": False,
            "google_auth_available": bool(_client_id()),
            "message": "No Google Drive tokens stored for this user",
        }

    return {
        "user_id": user_id,
        "email": user["email"],
        "tokens_found": True,
        "google_auth_available": True,
        "access_token_length": len(token["access_token"] or ""),
        "has_refresh_token": bool(token["refresh_token"]),
        "token_expiry": token["token_expiry"],
        "created_at": token["created_at"],
        "updated_at": token["updated_at"],
    }


@auth_router.get("/google/drive-picker")
async def google_drive_picker(user_id: int = Query(...)):
    conn = get_db()
    token = conn.execute(
        "SELECT access_token FROM google_drive_tokens WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Google Drive not authorized. Please connect Google Drive first.",
        )
    return {
        "success": True,
        "picker_url": "https://drive.google.com/drive/u/0/my-drive",
        "user_id": user_id,
    }


# ── Uploads: list / import ───────────────────────────────────────────────────


@uploads_router.post("/google-drive/auth/init")
async def initialize_google_drive_auth(user_id: int = Query(...)):
    user = _ensure_user(user_id)
    conn = get_db()
    token = conn.execute(
        "SELECT access_token FROM google_drive_tokens WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Google Drive not authorized. Please connect via OAuth.",
        )
    return {
        "success": True,
        "user_id": user_id,
        "email": user["email"],
        "authorized": True,
        "message": f"Google Drive authorized for {user['email']}",
    }


@uploads_router.get("/google-drive/files")
async def list_google_drive_files(
    user_id: int = Query(...),
    query: Optional[str] = Query(None),
):
    _ensure_user(user_id)
    service = GoogleDriveService(user_id)
    if not service.initialize_service():
        raise HTTPException(
            status_code=401,
            detail="Google Drive not authorized. Please connect Google Drive first.",
        )
    files = service.list_files(query=query) or []
    return {"success": True, "files": files}


@uploads_router.post("/google-drive/import")
async def import_from_google_drive(
    request: Request,
    user_id: int = Query(...),
    file_id: str = Query(...),
    template_id: int = Query(...),
):
    return _save_drive_file_as_document(
        request=request,
        user_id=user_id,
        template_id=template_id,
        file_id=file_id,
    )


@uploads_router.post("/download-from-google-drive")
async def download_from_google_drive(
    request: Request,
    user_id: int = Query(...),
    file_id: str = Query(...),
    filename: str = Query(...),
    template_id: int = Query(...),
):
    return _save_drive_file_as_document(
        request=request,
        user_id=user_id,
        template_id=template_id,
        file_id=file_id,
        filename=filename,
    )
