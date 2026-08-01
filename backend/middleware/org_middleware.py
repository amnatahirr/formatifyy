"""
middleware/org_middleware.py — Resolve organization per request (multi-tenancy).

Backward compatible: missing API key / org code → default org_id = 1.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from database import get_db


def _row_to_org(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": row["name"] or "",
        "code": row["code"] or "",
        "type": row["type"] or "university",
        "api_key": row["api_key"] or "",
        "plan": row["plan"] or "university",
        "modules": row["modules"] or "core",
        "documents_used": int(row["documents_used"] or 0),
        "documents_limit": int(row["documents_limit"] or 999999),
        "is_active": bool(row["is_active"]),
        "primary_color": row["primary_color"] or "#7B61FF",
        "logo_url": row["logo_url"],
        "created_at": row["created_at"] or "",
    }


def get_default_organization() -> dict[str, Any]:
    """Always available fallback — org id 1 (seeded COMSATS)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM organizations WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return _row_to_org(row)
        cursor.execute("SELECT * FROM organizations ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return _row_to_org(row)
    finally:
        conn.close()
    # Hard fallback if DB not seeded yet
    return {
        "id": 1,
        "name": "COMSATS University Islamabad",
        "code": "COMSATS-LHR",
        "type": "university",
        "api_key": "fmt_live_comsats_default",
        "plan": "university",
        "modules": "core,fyp",
        "documents_used": 0,
        "documents_limit": 999999,
        "is_active": True,
        "primary_color": "#7B61FF",
        "logo_url": None,
        "created_at": "",
    }


def lookup_organization(
    *,
    api_key: Optional[str] = None,
    org_code: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve org by Bearer API key or X-Org-Code; else default org 1."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        row = None
        key = (api_key or "").strip()
        code = (org_code or "").strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        if key:
            cursor.execute(
                "SELECT * FROM organizations WHERE api_key = ? COLLATE NOCASE",
                (key,),
            )
            row = cursor.fetchone()
        if row is None and code:
            cursor.execute(
                "SELECT * FROM organizations WHERE code = ? COLLATE NOCASE",
                (code,),
            )
            row = cursor.fetchone()
        if row is None:
            return get_default_organization()
        org = _row_to_org(row)
        if not org["is_active"]:
            raise HTTPException(status_code=403, detail="Organization is inactive.")
        if org["documents_used"] >= org["documents_limit"]:
            raise HTTPException(
                status_code=403,
                detail="Organization document limit exceeded. Contact your administrator.",
            )
        return org
    finally:
        conn.close()


def _org_by_id(org_id: int) -> dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (int(org_id),))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Organization not found for token.")
        org = _row_to_org(row)
        if not org["is_active"]:
            raise HTTPException(status_code=403, detail="Organization is inactive.")
        return org
    finally:
        conn.close()


def resolve_organization_from_request(request: Request) -> dict[str, Any]:
    """
    Resolve tenant in order:
    1) JWT Bearer (preferred — clients never send org api_key)
    2) X-Org-Code / org_code query (login gate / public resolve)
    3) Legacy fmt_live_ org API key (server-side / internal only)
    4) Default org id=1
    """
    from auth_jwt import bearer_token_from_header, decode_access_token, looks_like_jwt

    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    token = bearer_token_from_header(auth)
    if token and looks_like_jwt(token):
        claims = decode_access_token(token)
        org = _org_by_id(int(claims["org_id"]))
        request.state.jwt_claims = claims
        request.state.user_id = int(claims.get("user_id") or claims.get("sub") or 0)
        request.state.user_role = (claims.get("role") or "").strip()
        return org

    org_code = request.headers.get("X-Org-Code") or request.headers.get("x-org-code")
    if not org_code:
        org_code = request.query_params.get("org_code") or request.query_params.get("orgCode")

    # Legacy internal api_key only when token looks like fmt_live_…
    api_key = None
    if token and token.startswith("fmt_live_"):
        api_key = token
    elif not token:
        # Do not accept api_key from query for public clients anymore.
        pass

    return lookup_organization(api_key=api_key, org_code=org_code)


def resolve_org_id_for_user_action(request: Request, user_id: int | None = None) -> int:
    """
    Org for authenticated mutations.

    Prefer JWT. If the request fell through to the default org (no JWT / key),
    use the acting user's org_id so writes are not silently tagged as org 1.
    """
    org = resolve_organization_from_request(request)
    org_id = int(org["id"])
    if getattr(request.state, "jwt_claims", None):
        return org_id
    if not user_id:
        return org_id

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT org_id FROM users WHERE id = ?", (int(user_id),))
        row = cursor.fetchone()
        if row and row["org_id"] is not None:
            return int(row["org_id"])
    finally:
        conn.close()
    return org_id


async def get_organization(request: Request) -> dict[str, Any]:
    """
    FastAPI dependency / helper.
    Attaches org to request.state when possible and returns the org dict.
    """
    org = getattr(request.state, "org", None)
    if isinstance(org, dict) and org.get("id"):
        return org
    org = resolve_organization_from_request(request)
    request.state.org = org
    request.state.org_id = org["id"]
    return org


def public_org_payload(org: dict[str, Any]) -> dict[str, Any]:
    """Client-safe org fields — never includes api_key."""
    modules = [m.strip() for m in (org.get("modules") or "core").split(",") if m.strip()]
    # Self-registration is available for every org plan (university / starter / enterprise).
    return {
        "org_id": org.get("id"),
        "org_name": org.get("name"),
        "org_code": org.get("code"),
        "plan": org.get("plan"),
        "type": org.get("type"),
        "modules": modules,
        "has_fyp": "fyp" in modules,
        "has_core": "core" in modules or True,
        "allow_self_signup": True,
        "primary_color": org.get("primary_color") or "#7B61FF",
        "logo_url": org.get("logo_url"),
        "documents_used": org.get("documents_used", 0),
        "documents_limit": org.get("documents_limit", 999999),
    }


# Admin FYP-only path prefixes (core admin routes stay open)
_FYP_PATH_PREFIXES = (
    "/api/supervisor",
    "/api/student",
    "/api/admin/supervisors",
    "/api/admin/deadlines",
    "/api/admin/semester-deadlines",
)


def _path_requires_fyp(path: str) -> bool:
    if "/frontmatter" in path:
        return True
    for prefix in _FYP_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            return True
    return False


class OrganizationMiddleware(BaseHTTPMiddleware):
    """Attach org to every request; enforce FYP module only on FYP routes."""

    async def dispatch(self, request: Request, call_next):
        # Skip CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        try:
            org = resolve_organization_from_request(request)
        except HTTPException as exc:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        request.state.org = org
        request.state.org_id = org["id"]

        path = request.url.path
        if _path_requires_fyp(path):
            modules = [m.strip() for m in (org.get("modules") or "core").split(",") if m.strip()]
            if "fyp" not in modules:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Your plan does not include the fyp module. Please upgrade.",
                    },
                )

        return await call_next(request)


def get_super_admin_key() -> str:
    return os.getenv("SUPER_ADMIN_KEY", "super_secret_master_key_here")
