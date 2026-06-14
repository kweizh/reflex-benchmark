import reflex as rx
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import secrets
import base64
import hashlib
import json
import os
import httpx
from urllib.parse import urlencode

# 1. Generate or load credentials
CREDENTIALS_FILE = "/home/user/oauth_app/credentials.json"

if not os.path.exists(CREDENTIALS_FILE):
    creds = {
        "client_id": secrets.token_urlsafe(16),
        "client_secret": secrets.token_urlsafe(32),
        "redirect_uri": "http://localhost:8000/auth/callback",
        "username": "demo_user_" + secrets.token_hex(4)
    }
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f)
else:
    with open(CREDENTIALS_FILE, "r") as f:
        creds = json.load(f)

CLIENT_ID = creds["client_id"]
CLIENT_SECRET = creds["client_secret"]
REDIRECT_URI = creds["redirect_uri"]
USERNAME = creds["username"]

# In-memory stores
auth_codes = {} # code -> { "code_challenge": ..., "redirect_uri": ... }
app_states = {} # state -> code_verifier
latest_token = None

# 2. FastAPI App
fastapi_app = FastAPI()

# --- Mock Provider Endpoints ---

@fastapi_app.get("/auth/authorize")
def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str,
    code_challenge: str,
    code_challenge_method: str,
    state: str
):
    if client_id != CLIENT_ID:
        return JSONResponse(status_code=400, content={"error": "invalid_client"})
    if response_type != "code":
        return JSONResponse(status_code=400, content={"error": "unsupported_response_type"})
    if code_challenge_method != "S256":
        return JSONResponse(status_code=400, content={"error": "invalid_request"})
    
    code = secrets.token_urlsafe(32)
    auth_codes[code] = {
        "code_challenge": code_challenge,
        "redirect_uri": redirect_uri
    }
    
    # redirect back to application
    return RedirectResponse(f"{redirect_uri}?code={code}&state={state}", status_code=302)

@fastapi_app.post("/auth/token")
def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    code_verifier: str = Form(...)
):
    if grant_type != "authorization_code":
        return JSONResponse(status_code=400, content={"error": "unsupported_grant_type"})
    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        return JSONResponse(status_code=400, content={"error": "invalid_client"})
    
    if code not in auth_codes:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})
    
    code_data = auth_codes.pop(code)
    if code_data["redirect_uri"] != redirect_uri:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})
    
    # PKCE S256 verification
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    expected_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip("=")
    
    if expected_challenge != code_data["code_challenge"]:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})
    
    global latest_token
    access_token = secrets.token_urlsafe(32)
    latest_token = access_token
    
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600
    }

# --- Application Endpoints ---

@fastapi_app.get("/auth/start")
def start_auth():
    code_verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(32)
    app_states[state] = code_verifier
    
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip("=")
    
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state
    }
    
    url = f"/auth/authorize?{urlencode(params)}"
    return RedirectResponse(url, status_code=302)

@fastapi_app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    if state not in app_states:
        return JSONResponse(status_code=400, content={"error": "invalid_state"})
    
    code_verifier = app_states.pop(state)
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/auth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code_verifier": code_verifier
            }
        )
    
    if resp.status_code != 200:
        return JSONResponse(status_code=400, content={"error": "token_exchange_failed"})
    
    token_data = resp.json()
    access_token = token_data["access_token"]
    
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=False, path="/")
    return response

# --- API Endpoint ---

@fastapi_app.get("/api/me")
def get_me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    
    token = auth_header.split(" ")[1]
    if token != latest_token or latest_token is None:
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    
    return {"username": USERNAME}


# 3. Reflex UI and State

class State(rx.State):
    access_token: str = rx.Cookie(name="access_token")
    _access_token: str = ""
    
    def on_load(self):
        self._access_token = self.access_token

def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Sign in"),
        rx.link("Sign in with OAuth", href="/auth/start"),
        rx.cond(
            State.access_token != "",
            rx.text(f"Token: {State.access_token}"),
            rx.text("Not logged in")
        )
    )

app = rx.App(api_transformer=fastapi_app)
app.add_page(index, on_load=State.on_load)
