"""Application-side PKCE flow endpoints.

Provides:
  GET /auth/start     – initiates PKCE flow
  GET /auth/callback  – exchanges code for token, sets cookie
"""

from __future__ import annotations

import hashlib
import secrets
from base64 import urlsafe_b64encode
from urllib.parse import urlencode

import httpx
from fastapi import Request
from fastapi.responses import RedirectResponse

from .credentials import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

# state → code_verifier
_state_verifiers: dict[str, str] = {}


def _b64url_no_pad(data: bytes) -> str:
    """Base64url-encode *data* without trailing ``=`` padding."""
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _compute_s256(verifier: str) -> str:
    """Return the S256 code challenge for *verifier*."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return _b64url_no_pad(digest)


async def start(request: Request) -> RedirectResponse:
    """Initiate the PKCE authorization code flow.

    Generates code_verifier / code_challenge, stores the verifier
    keyed by state, and redirects to the authorization endpoint.
    """
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = _compute_s256(code_verifier)
    state = secrets.token_urlsafe(32)

    _state_verifiers[state] = code_verifier

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    location = f"/auth/authorize?{urlencode(params)}"
    return RedirectResponse(url=location, status_code=302)


async def callback(request: Request) -> RedirectResponse:
    """OAuth2 callback – exchange code for token and set cookie."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        return RedirectResponse(url="/", status_code=302)

    code_verifier = _state_verifiers.pop(state, None)
    if code_verifier is None:
        return RedirectResponse(url="/", status_code=302)

    # Exchange code for token at the provider's token endpoint
    token_url = "http://localhost:8000/auth/token"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code_verifier": code_verifier,
            },
        )

    if resp.status_code != 200:
        return RedirectResponse(url="/", status_code=302)

    token_data = resp.json()
    access_token = token_data["access_token"]

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        path="/",
        httponly=False,
    )
    return response
