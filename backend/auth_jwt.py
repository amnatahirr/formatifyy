"""
auth_jwt.py — Issue / verify Formatify access tokens.

Token claims: sub (user_id), org_id, role, email, org_code
Clients send: Authorization: Bearer <jwt>
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import HTTPException

ALGORITHM = "HS256"
DEFAULT_EXPIRE_HOURS = 24 * 7  # 7 days


def _secret() -> str:
    s = os.environ.get("JWT_SECRET")
    if not s:
        raise RuntimeError("JWT_SECRET is not set")
    return s


def create_access_token(
    *,
    user_id: int,
    org_id: int,
    role: str,
    email: str,
    org_code: str = "",
    expires_hours: int = DEFAULT_EXPIRE_HOURS,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "user_id": int(user_id),
        "org_id": int(org_id),
        "role": role,
        "email": email,
        "org_code": org_code or "",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_hours)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc

    if payload.get("typ") not in (None, "access"):
        raise HTTPException(status_code=401, detail="Invalid token type.")
    return payload


def bearer_token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    raw = authorization.strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw.strip() or None


def looks_like_jwt(token: str) -> bool:
    """Heuristic: JWTs are three base64 segments; org API keys start with fmt_live_."""
    if not token or token.startswith("fmt_live_"):
        return False
    return token.count(".") == 2
