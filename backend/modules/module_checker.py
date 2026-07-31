"""
modules/module_checker.py — Gate features by organization modules.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from modules.fyp_module import check_fyp_access


def _modules_list(org: Any) -> list[str]:
    if org is None:
        return ["core"]
    if isinstance(org, dict):
        raw = org.get("modules", "core") or "core"
    else:
        raw = getattr(org, "modules", "core") or "core"
    return [m.strip() for m in str(raw).split(",") if m.strip()]


def has_module(org: Any, module_name: str) -> bool:
    return module_name in _modules_list(org)


def require_module(org: Any, module_name: str) -> None:
    """
    Raise HTTP 403 if org doesn't have this module.
    Usage: require_module(org, 'fyp')
    """
    if not has_module(org, module_name):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Your plan does not include the {module_name} module. "
                "Please upgrade."
            ),
        )


async def require_fyp_from_request(request: Request) -> dict:
    """FastAPI dependency for FYP-only routers."""
    from middleware.org_middleware import get_organization

    org = await get_organization(request)
    require_module(org, "fyp")
    return org


def assert_fyp(org: Any) -> None:
    if not check_fyp_access(org):
        require_module(org, "fyp")
