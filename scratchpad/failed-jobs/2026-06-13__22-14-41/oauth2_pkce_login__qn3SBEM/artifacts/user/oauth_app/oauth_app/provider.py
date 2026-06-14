"""Mock OAuth2 authorization server with PKCE S256 support.

Provides:
  GET  /auth/authorize  – authorization endpoint
  POST /auth/token       – token endpoint
"""

from __future__ import annotations

import hashlib
import secrets
from base64 import urlsafe_b64encode

from fastapi import Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .credentials import CLIENT_ID, CLIENT_SECRET, USERNAME

# ── In-memory stores (single-process server) ──────────────────────────

# code → {code_challenge, redirect_uri}
_pending_auth: dict[str, dict[str, str]] = {}

# The single valid access token (most recently issued)
_current_access_token: str | None = None


def _b64url_no_pad(data: bytes) -> str:
    """Base64url-encode *data* without trailing ``=`` padding."""
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _compute_s256(verifier: str) -> str:
    """Return the S256 code challenge for *verifier*."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return _b64url_no_pad(digest)


# ── /auth/authorize ────────────────────────────────────────────────────

async def authorize(request: Request) -> RedirectResponse | JSONResponse:
    """Authorization endpoint.

    Validates query params and redirects with an authorization code.
    """
    params = request.query_params

    client_id = params.get("client_id")
    redirect_uri = params.get("redirect_uri")
    response_type = params.get("response_type")
    code_challenge = params.get("code_challenge")
    code_challenge_method = params.get("code_challenge_method")
    state = params.get("state")

    # Validate required fields
    errors: list[str] = []
    if client_id != CLIENT_ID:
        errors.append("invalid client_id")
    if not redirect_uri:
        errors.append("missing redirect_uri")
    if response_type != "code":
        errors.append("unsupported response_type")
    if not code_challenge:
        errors.append("missing code_challenge")
    if code_challenge_method != "S256":
        errors.append("unsupported code_challenge_method")
    if not state:
        errors.append("missing state")

    if errors:
        return JSONResponse(
            status_code=400,
            content={"error": "; ".join(errors)},
        )

    # Generate authorization code
    code = secrets.token_urlsafe(32)
    _pending_auth[code] = {
        "code_challenge": code_challenge,
        "redirect_uri": redirect_uri,
    }

    # Build redirect
    location = f"{redirect_uri}?code={code}&state={state}"
    return RedirectResponse(url=location, status_code=302)


# ── /auth/token ────────────────────────────────────────────────────────

async def token(
    request: Request,
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    code_verifier: str = Form(...),
) -> JSONResponse:
    """Token endpoint – exchanges authorization code for access token."""

    # Validate client credentials
    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_client"},
        )

    # Validate grant_type
    if grant_type != "authorization_code":
        return JSONResponse(
            status_code=400,
            content={"error": "unsupported_grant_type"},
        )

    # Look up pending auth
    pending = _pending_auth.pop(code, None)
    if pending is None:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant"},
        )

    # Validate redirect_uri
    if pending["redirect_uri"] != redirect_uri:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant"},
        )

    # PKCE S256 enforcement
    expected_challenge = pending["code_challenge"]
    actual_challenge = _compute_s256(code_verifier)
    if actual_challenge != expected_challenge:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant"},
        )

    # Issue token
    global _current_access_token
    _current_access_token = secrets.token_urlsafe(32)

    return JSONResponse(
        status_code=200,
        content={
            "access_token": _current_access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )


def get_current_token() -> str | None:
    """Return the currently valid access token, or None."""
    return _current_access_token
