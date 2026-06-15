"""Reflex app with a custom FastAPI JWT sub-app mounted via api_transformer."""

import secrets

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

import reflex as rx
from rxconfig import config

# ---------------------------------------------------------------------------
# JWT configuration – secret is generated once at import time using a
# cryptographically-secure random API (never read from environment / hardcoded).
# ---------------------------------------------------------------------------
_JWT_SECRET: str = secrets.token_urlsafe(32)
_JWT_ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# FastAPI sub-app – provides POST /api/login and GET /api/me
# ---------------------------------------------------------------------------
fastapi_app = FastAPI()


class LoginRequest(BaseModel):
    username: str
    password: str


@fastapi_app.post("/api/login")
async def login(body: LoginRequest):
    """Validate credentials and return a signed JWT."""
    if body.username != "admin" or body.password != "secret":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode(
        {"sub": body.username},
        _JWT_SECRET,
        algorithm=_JWT_ALGORITHM,
    )
    return {"access_token": token}


@fastapi_app.get("/api/me")
async def me(REDACTED Header(...)):
    """Return the authenticated user's identity from the JWT."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"user": payload["sub"]}


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------
class State(rx.State):
    """Application state.

    ``_current_user`` is a backend-only var (leading underscore) that holds
    the decoded user identity after authentication.  ``is_logged_in`` is the
    corresponding frontend-visible flag.
    """

    is_logged_in: bool = False
    _current_user: str = ""

    async def do_login(self):
        """Call /api/login then /api/me and update state accordingly."""
        async with httpx.AsyncClient() as client:
            # Step 1 – obtain token
            login_resp = await client.post(
                "http://localhost:8000/api/login",
                json={"username": "admin", "password": "secret"},
            )
            if login_resp.status_code != 200:
                self.is_logged_in = False
                self._current_user = ""
                return

            token = login_resp.json()["access_token"]

            # Step 2 – fetch identity
            me_resp = await client.get(
                "http://localhost:8000/api/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me_resp.status_code != 200:
                self.is_logged_in = False
                self._current_user = ""
                return

            user = me_resp.json()["user"]
            self._current_user = user
            self.is_logged_in = True


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Reflex + FastAPI JWT Demo", size="8"),
            rx.text(
                rx.cond(
                    State.is_logged_in,
                    "✅ Logged in!",
                    "❌ Not logged in.",
                ),
                size="5",
            ),
            rx.button(
                "Login as admin",
                on_click=State.do_login,
                color_scheme="blue",
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


# ---------------------------------------------------------------------------
# Wire FastAPI into Reflex via api_transformer
# ---------------------------------------------------------------------------
app = rx.App(api_transformer=fastapi_app)
app.add_page(index)
