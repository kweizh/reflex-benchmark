"""Reflex app with custom FastAPI JWT router mounted via api_transformer."""

import secrets

import jwt
import reflex as rx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from rxconfig import config

# ---------------------------------------------------------------------------
# Generate a random JWT signing secret at application startup.
# ---------------------------------------------------------------------------
JWT_SECRET = secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# FastAPI sub-application with login + me endpoints
# ---------------------------------------------------------------------------
fastapi_app = FastAPI()


@fastapi_app.post("/api/login")
async def login(request: Request):
    """Authenticate user and return a JWT access token."""
    body = await request.json()
    username = body.get("username")
    password = body.get("password")

    if username != "admin" or password != "secret":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode({"sub": username}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return JSONResponse({"access_token": token})


@fastapi_app.get("/api/me")
async def me(request: Request):
    """Return the current user from a valid Bearer token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[len("Bearer "):]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return JSONResponse({"user": payload["sub"]})


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------
class State(rx.State):
    """Application state with backend-only JWT user storage."""

    # Backend-only var – never synced to the browser.
    _current_user: str = ""

    # Frontend-visible var.
    is_logged_in: bool = False

    async def do_login(self):
        """Call POST /api/login then GET /api/me, updating state."""
        import httpx

        async with httpx.AsyncClient() as client:
            # 1. Login
            login_resp = await client.post(
                "http://localhost:8000/api/login",
                json={"username": "admin", "password": "secret"},
            )
            if login_resp.status_code != 200:
                self.is_logged_in = False
                self._current_user = ""
                return

            token = login_resp.json()["access_token"]

            # 2. Fetch current user
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
# Pages
# ---------------------------------------------------------------------------
def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
            rx.text(
                "Get started by editing ",
                rx.code(f"{config.app_name}/{config.app_name}.py"),
                size="5",
            ),
            rx.cond(
                State.is_logged_in,
                rx.text("✅ Logged in as admin", color="green", size="4"),
                rx.text("❌ Not logged in", color="red", size="4"),
            ),
            rx.button("Login", on_click=State.do_login),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


# ---------------------------------------------------------------------------
# Reflex app – mount the FastAPI sub-app via api_transformer
# ---------------------------------------------------------------------------
app = rx.App(api_transformer=fastapi_app)
app.add_page(index)
