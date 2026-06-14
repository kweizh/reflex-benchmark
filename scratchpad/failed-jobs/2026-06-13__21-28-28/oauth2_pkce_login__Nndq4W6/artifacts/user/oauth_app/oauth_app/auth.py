"""FastAPI app implementing mock OAuth2 provider and application-side PKCE flow."""

import base64
import hashlib
import secrets
from typing import Dict, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .credentials import ACCESS_TOKEN, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, USERNAME

fastapi_app = FastAPI()

# ── Module-level storage (single-process) ─────────────────────────
# state → code_verifier  (populated by /auth/start, consumed by /auth/callback)
_state_store: Dict[str, str] = {}

# code → {"code_challenge": str, "redirect_uri": str}  (populated by /auth/authorize, consumed by /auth/token)
_code_store: Dict[str, dict] = {}

# The most recently issued access token
_current_token: str = ACCESS_TOKEN


# ── Helpers ───────────────────────────────────────────────────────

def _b64url_no_pad(data: bytes) -> str:
    """Base64url-encode *data* without ``=`` padding (RFC 7636 §Appendix B)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _s256_challenge(verifier: str) -> str:
    """Compute the S256 code_challenge from a code_verifier."""
    return _b64url_no_pad(hashlib.sha256(verifier.encode("ascii")).digest())


# ── Home page ─────────────────────────────────────────────────────

@fastapi_app.get("/", response_class=HTMLResponse)
async def index():
    """Simple home page with a Sign-in link."""
    return """<!DOCTYPE html>
<html>
<head><title>OAuth2 PKCE Demo</title></head>
<body>
<h1>Sign in</h1>
<a href="/auth/start">Sign in</a>
</body>
</html>"""


# ── Mock OAuth provider endpoints ────────────────────────────────

@fastapi_app.get("/auth/authorize")
async def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(...),
    state: str = Query(...),
):
    """Authorization endpoint for the mock OAuth provider."""

    # Validate required fields
    if client_id != CLIENT_ID:
        return JSONResponse(status_code=400, content={"error": "invalid_client"})
    if response_type != "code":
        return JSONResponse(status_code=400, content={"error": "unsupported_response_type"})
    if code_challenge_method != "S256":
        return JSONResponse(status_code=400, content={"error": "invalid_request"})
    if not code_challenge:
        return JSONResponse(status_code=400, content={"error": "invalid_request"})

    # Issue an authorization code
    code = secrets.token_urlsafe(32)

    # Store code → {code_challenge, redirect_uri}
    _code_store[code] = {
        "code_challenge": code_challenge,
        "redirect_uri": redirect_uri,
    }

    # Redirect back with code and state
    params = {"code": code, "state": state}
    location = f"{redirect_uri}?{urlencode(params)}"
    return RedirectResponse(url=location, status_code=302)


@fastapi_app.post("/auth/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    code_verifier: str = Form(...),
):
    """Token endpoint for the mock OAuth provider."""

    global _current_token

    # Validate client credentials
    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        return JSONResponse(status_code=400, content={"error": "invalid_client"})

    if grant_type != "authorization_code":
        return JSONResponse(status_code=400, content={"error": "unsupported_grant_type"})

    # Look up the code
    code_data = _code_store.pop(code, None)
    if code_data is None:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    # Validate redirect_uri matches
    if redirect_uri != code_data["redirect_uri"]:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    # PKCE S256 verification
    expected_challenge = _s256_challenge(code_verifier)
    if expected_challenge != code_data["code_challenge"]:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    # Issue a new access token
    _current_token = secrets.token_urlsafe(48)

    return JSONResponse(
        content={
            "access_token": _current_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    )


# ── Application-side flow endpoints ──────────────────────────────

@fastapi_app.get("/auth/start")
async def auth_start(request: Request):
    """Initiate the PKCE OAuth2 flow.

    Generates a code_verifier, derives the S256 code_challenge, stores the
    verifier keyed by an opaque state, and redirects to /auth/authorize.
    """
    code_verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(32)

    # Store state → code_verifier
    _state_store[state] = code_verifier

    code_challenge = _s256_challenge(code_verifier)

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    # Redirect to the mock provider's authorization endpoint
    # Build absolute URL based on the current request
    base_url = str(request.base_url).rstrip("/")
    location = f"{base_url}/auth/authorize?{urlencode(params)}"
    return RedirectResponse(url=location, status_code=302)


@fastapi_app.get("/auth/callback")
async def auth_callback(code: str = Query(...), state: str = Query(...)):
    """OAuth2 callback – exchanges the code for a token and sets a cookie."""

    global _current_token

    # Look up the verifier for this state
    code_verifier = _state_store.pop(state, None)
    if code_verifier is None:
        return JSONResponse(status_code=400, content={"error": "invalid_state"})

    # Exchange the code at the token endpoint (server-to-server call)
    import httpx

    token_url = "http://localhost:8000/auth/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code_verifier": code_verifier,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(token_url, data=data)

    if resp.status_code != 200:
        return JSONResponse(
            status_code=502,
            content={"error": "token_exchange_failed", "detail": resp.text},
        )

    token_data = resp.json()
    access_token_value = token_data["access_token"]
    _current_token = access_token_value

    # Redirect to home with the access_token cookie (non-HttpOnly, Path=/)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token_value,
        path="/",
        httponly=False,
        samesite="lax",
    )
    return response


# ── Protected API endpoint ────────────────────────────────────────

@fastapi_app.get("/api/me")
async def api_me(request: Request):
    """Return the demo user identity if a valid Bearer token is present."""
    auth_header: Optional[str] = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    token = auth_header[len("Bearer "):]
    if token != _current_token:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return JSONResponse(content={"username": USERNAME})