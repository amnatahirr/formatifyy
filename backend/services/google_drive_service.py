"""Google Drive API helper — list / download / upload using per-user OAuth tokens."""

from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from config import settings
from database import get_db

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Native Google Workspace types → export mime + preferred extension
_GOOGLE_EXPORT = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}

_SKIP_GOOGLE_APPS = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.shortcut",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.site",
}


class GoogleDriveService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.service = None
        self.credentials = None

    def _load_tokens_from_db(self):
        conn = get_db()
        token = conn.execute(
            """
            SELECT access_token, refresh_token, token_expiry
            FROM google_drive_tokens
            WHERE user_id = ?
            """,
            (self.user_id,),
        ).fetchone()
        conn.close()
        return token

    def _save_tokens_to_db(self, credentials: Credentials) -> None:
        conn = get_db()
        conn.execute(
            """
            INSERT OR REPLACE INTO google_drive_tokens
            (user_id, access_token, refresh_token, token_expiry, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                self.user_id,
                credentials.token,
                credentials.refresh_token,
                credentials.expiry.isoformat() if credentials.expiry else None,
            ),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _parse_token_expiry(token_expiry):
        if token_expiry is None:
            return None
        if isinstance(token_expiry, datetime):
            return token_expiry
        if isinstance(token_expiry, str):
            for fmt in (
                None,  # fromisoformat
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
            ):
                try:
                    if fmt is None:
                        return datetime.fromisoformat(token_expiry)
                    return datetime.strptime(token_expiry, fmt)
                except ValueError:
                    continue
            # expires_in seconds stored as plain int string → force refresh
            try:
                int(token_expiry)
                return datetime.utcnow()
            except ValueError:
                pass
        if isinstance(token_expiry, (int, float)):
            # Relative expires_in from OAuth response — force refresh if token looks stale
            try:
                return datetime.fromtimestamp(token_expiry)
            except (ValueError, OSError):
                return None
        return None

    def get_credentials(self) -> Optional[Credentials]:
        token = self._load_tokens_from_db()
        if not token:
            return None

        client_id = settings.GOOGLE_DRIVE_CLIENT_ID or settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_DRIVE_CLIENT_SECRET or settings.GOOGLE_CLIENT_SECRET
        if not client_id or not client_secret:
            return None

        credentials = Credentials(
            token=token["access_token"],
            refresh_token=token["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )

        token_expiry = self._parse_token_expiry(token["token_expiry"])
        if token_expiry:
            credentials.expiry = token_expiry

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_tokens_to_db(credentials)

        return credentials

    def initialize_service(self) -> bool:
        credentials = self.get_credentials()
        if not credentials:
            return False
        self.credentials = credentials
        self.service = build("drive", "v3", credentials=credentials)
        return True

    def list_files(
        self, query: Optional[str] = None, page_size: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.initialize_service():
            return None

        q = query or (
            "trashed = false and mimeType != 'application/vnd.google-apps.folder'"
        )
        results = (
            self.service.files()
            .list(
                q=q,
                pageSize=page_size,
                fields="files(id, name, mimeType, size, webViewLink, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return results.get("files", [])

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        if not self.initialize_service():
            return {}
        return (
            self.service.files()
            .get(fileId=file_id, fields="id, name, mimeType, size")
            .execute()
        )

    def download_file(self, file_id: str, dest_path: str) -> bool:
        """Download a Drive file (binary) or export a Google Docs Editors file."""
        if not self.initialize_service():
            return False

        meta = self.get_file_metadata(file_id)
        mime = (meta.get("mimeType") or "").strip()
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

        # Resolve Drive shortcuts to the real target file.
        if mime == "application/vnd.google-apps.shortcut":
            full = (
                self.service.files()
                .get(fileId=file_id, fields="shortcutDetails")
                .execute()
            )
            target_id = (full.get("shortcutDetails") or {}).get("targetId")
            if not target_id:
                raise ValueError("Google Drive shortcut has no target file")
            return self.download_file(target_id, dest_path)

        use_export = mime in _GOOGLE_EXPORT or (
            mime.startswith("application/vnd.google-apps.")
            and mime not in _SKIP_GOOGLE_APPS
        )

        def _write(request) -> None:
            with io.FileIO(dest_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

        if use_export:
            export_mime, _ = _GOOGLE_EXPORT.get(
                mime,
                # Unknown Workspace type: try Word export (covers most Docs Editors cases)
                (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".docx",
                ),
            )
            _write(
                self.service.files().export_media(
                    fileId=file_id, mimeType=export_mime
                )
            )
        else:
            try:
                _write(self.service.files().get_media(fileId=file_id))
            except HttpError as exc:
                # Filename may look like .docx while Drive stores a Docs Editors file.
                body = getattr(exc, "content", b"") or b""
                text = body.decode("utf-8", errors="ignore") if isinstance(body, (bytes, bytearray)) else str(body)
                if exc.resp is not None and int(exc.resp.status) == 403 and (
                    "fileNotDownloadable" in text
                    or "Only files with binary content" in text
                    or "Use Export" in text
                ):
                    export_mime = (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    _write(
                        self.service.files().export_media(
                            fileId=file_id, mimeType=export_mime
                        )
                    )
                else:
                    raise

        return os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0

    def upload_file(self, file_path: str, name: str, folder_id: Optional[str] = None):
        if not self.initialize_service():
            return None
        file_metadata: Dict[str, Any] = {"name": name}
        if folder_id:
            file_metadata["parents"] = [folder_id]
        media = MediaFileUpload(file_path, resumable=True)
        return (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
            .execute()
        )
