import reflex as rx
from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import RedirectResponse, JSONResponse
import secrets
import hashlib
import base64
import json
import os
from typing import Dict, Optional
import httpx

# --- Constants & Persistence ---
CREDENTIALS_PATH = "/home/user/oauth_app/credentials.json"

def generate_credentials():
    if not os.path.exists(CREDENTIALS_PATH):
        creds = {
            "client_id": secrets.token_urlsafe(16),
            "client_secret": secrets.token_urlsafe(32),
            "redirect_uri": "http://localhost:8000/auth/callback",
            "username": f"user_{secrets.token_hex(4)}"
        }
        with open(CREDENTIALS_PATH, "w") as f:
            json.dump(creds, f, indent=2)
    with open(CREDENTIALS_PATH, "r") as f:
        return json.load(f)

CREDS = generate_credentials()

# --- In-Memory Stores ---
# state -> code_verifier
states_to_verifiers: Dict[str, str] = {}
# code -> {code_challenge, redirect_uri, client_id}
auth_codes: Dict[str, dict] = {}
# token -> username
valid_tokens: Dict[str, str] = {}
# Latest issued token for /api/me
latest_token: Optional[str] = None

# --- Helpers ---
def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").replace("=", "")

def compute_s256_challenge(verifier: str) -> str:
    sha256_hash = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64url_encode(sha256_hash)

# --- FastAPI App ---
fastapi_app = FastAPI()

# 1. Mock OAuth Provider Endpoints
@fastapi_app.get("/auth/authorize")
async def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str,
    code_challenge: str,
    code_challenge_method: str,
    state: str
):
    if client_id != CREDS["client_id"]:
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    if response_type != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)
    if code_challenge_method != "S256":
        return JSONResponse({"error": "invalid_request", "description": "Only S256 is supported"}, status_code=400)
    
    code = secrets.token_urlsafe(16)
    auth_codes[code] = {
        "code_challenge": code_challenge,
        "redirect_uri": redirect_uri,
        "client_id": client_id
    }
    
    return RedirectResponse(url=f"{redirect_uri}?code={code}&state={state}")

@fastapi_app.post("/auth/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    code_verifier: str = Form(...)
):
    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    
    if client_id != CREDS["client_id"] or client_secret != CREDS["client_secret"]:
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    
    auth_data = auth_codes.get(code)
    if not auth_data or auth_data["redirect_uri"] != redirect_uri or auth_data["client_id"] != client_id:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    
    # PKCE S256 enforcement
    if compute_s256_challenge(code_verifier) != auth_data["code_challenge"]:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    
    # Success!
    access_token = secrets.token_urlsafe(32)
    valid_tokens[access_token] = CREDS["username"]
    global latest_token
    latest_token = access_token
    
    # Cleanup code
    del auth_codes[code]
    
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600
    }

# 2. Application-side Flow Endpoints
@fastapi_app.get("/auth/start")
async def auth_start():
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    states_to_verifiers[state] = verifier
    
    challenge = compute_s256_challenge(verifier)
    
    params = {
        "client_id": CREDS["client_id"],
        "redirect_uri": CREDS["redirect_uri"],
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state
    }
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return RedirectResponse(url=f"/auth/authorize?{query_string}")

@fastapi_app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    verifier = states_to_verifiers.get(state)
    if not verifier:
        raise HTTPException(status_code=400, detail="Invalid state")
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/auth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CREDS["redirect_uri"],
                "client_id": CREDS["client_id"],
                "client_secret": CREDS["client_secret"],
                "code_verifier": verifier
            }
        )
    
    if response.status_code != 200:
        return JSONResponse(response.json(), status_code=response.status_code)
    
    token_data = response.json()
    access_token = token_data["access_token"]
    
    # Cleanup state
    del states_to_verifiers[state]
    
    response = RedirectResponse(url="/")
    # Set-Cookie access_token, not HttpOnly, Path=/
    response.set_cookie(
        key="access_token",
        value=access_token,
        path="/",
        httponly=False,
        max_age=3600,
        samesite="lax"
    )
    return response

# 3. Protected API
@fastapi_app.get("/api/me")
async def me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401)
    
    token = auth_header.split(" ")[1]
    if token != latest_token or token not in valid_tokens:
        raise HTTPException(status_code=401)
    
    return {"username": valid_tokens[token]}

# --- Reflex State & UI ---

class State(rx.State):
    access_token: rx.Cookie = rx.Cookie(name="access_token")
    _backend_token: str = ""

    @rx.var
    def token_mirror(self) -> str:
        # This ensures the backend state var mirrors the cookie
        self._backend_token = self.access_token
        return self._backend_token

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Sign in", size="9"),
            rx.link(
                rx.button("Login with OAuth2"),
                href="/auth/start",
            ),
            rx.text(f"Token: {State.access_token}"),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )

app = rx.App(api_transformer=fastapi_app)
app.add_page(index)
