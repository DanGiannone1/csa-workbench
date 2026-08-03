"""Application actor resolution for the one selected identity mode."""

from __future__ import annotations

import hmac
import os
import secrets
import threading
import time

from fastapi import HTTPException, Request
from workbench_core import appdb

from .identity_config import IdentityConfig

_LOCK = threading.Lock()
_TOKENS: dict[str, dict] = {}  # token -> {"userId": str, "issuedAt": float}
_ENTRA_SEEN: set[str] = set()  # uids provisioned this process — skips a Cosmos read per request

AUTH_HEADER = "X-Auth-Token"
# Idle demo sessions die after 12h — long enough for any demo, short enough to not
# accumulate forever in memory.
_TOKEN_TTL_SECONDS = 12 * 3600
# A failed sign-in costs one second — the only brute-force brake on a shared
# demo password now that no key-derivation work happens per attempt.
_FAILED_LOGIN_DELAY_SECONDS = 1.0


def _config() -> IdentityConfig:
    return IdentityConfig.from_env()


def login(username: str, password: str) -> dict:
    """Verify credentials → {token, user}. Raises 401 on failure (no reason leakage).

    The running DEMO_PASSWORD is the one shared demo credential; the database
    stores none, so rotating it is a config change plus restart."""
    config = _config()
    password_ok = (
        config.is_demo
        and bool(config.demo_password)
        and hmac.compare_digest((password or "").encode("utf-8"), config.demo_password.encode("utf-8"))
    )
    user = appdb.find_demo_user(username) if password_ok else None
    if user is None:
        time.sleep(_FAILED_LOGIN_DELAY_SECONDS)
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = secrets.token_urlsafe(32)
    with _LOCK:
        _TOKENS[token] = {"userId": user["id"], "issuedAt": time.time()}
    return {"token": token, "user": user}


def logout(token: str | None) -> None:
    if not token:
        return
    with _LOCK:
        _TOKENS.pop(token, None)


def _resolve(token: str | None) -> str | None:
    if not token:
        return None
    with _LOCK:
        entry = _TOKENS.get(token)
        if entry is None:
            return None
        if time.time() - entry["issuedAt"] > _TOKEN_TTL_SECONDS:
            _TOKENS.pop(token, None)
            return None
        return entry["userId"]


def _entra_user(claims: dict, config: IdentityConfig) -> str:
    """Map a VALIDATED Entra token (api_auth already checked signature, audience,
    tenant, issuer) to an app user, provisioning it on first sight."""
    raw_oid = claims.get("oid")
    raw_tid = claims.get("tid")
    if not isinstance(raw_tid, str) or not isinstance(raw_oid, str):
        raise HTTPException(status_code=401, detail="Unauthorized")
    oid = raw_oid.strip().lower()
    tid = raw_tid.strip().lower()
    if not tid or not oid or tid != (config.tenant_id or "").lower():
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = f"u-{oid}"
    if uid not in _ENTRA_SEEN:
        username = claims.get("preferred_username") or claims.get("upn") or claims.get("email") or uid
        display = claims.get("name") or username
        try:
            appdb.ensure_entra_user(tid, oid, username, display)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Unauthorized") from exc
        with _LOCK:
            _ENTRA_SEEN.add(uid)
    return uid


def current_user(request: Request) -> str:
    """FastAPI dependency: the signed-in user id, or 401. Every /sessions* route uses it.

    A request may carry only the credential appropriate for the configured mode.
    """
    config = _config()
    demo_token = request.headers.get(AUTH_HEADER)
    claims = getattr(request.state, "auth_claims", None)
    if demo_token and isinstance(claims, dict):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if config.is_demo:
        if isinstance(claims, dict):
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = _resolve(demo_token)
        if uid is not None:
            return uid
    elif config.is_entra and isinstance(claims, dict) and not demo_token:
        return _entra_user(claims, config)
    raise HTTPException(status_code=401, detail="Unauthorized")
