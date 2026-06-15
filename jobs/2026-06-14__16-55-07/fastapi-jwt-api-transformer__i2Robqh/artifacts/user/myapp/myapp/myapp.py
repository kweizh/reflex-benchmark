"""Reflex app with FastAPI JWT auth mounted via api_transformer."""

import secrets

import jwt
import reflex as rx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# JWT configuration – secret generated at startup via secrets.token_urlsafe
# ---------------------------------------------------------------------------
SECRET_KEY: str = secrets.token_urlsafe(32)
ALGORITHM: str = "HS256"

# ---------------------------------------------------------------------------
# FastAPI sub-app with /api/login and /api/me
# ---------------------------------------------------------------------------
api_app = FastAPI()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str


class MeResponse(BaseModel):
    user: str


security = HTTPBearer()


@api_app.post("/api/login")
def login(body: LoginRequest) -> TokenResponse:
    """Authenticate and return a JWT access token."""
    if body.username != "admin" or body.password != "secret":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode({"sub": "admin"}, SECRET_KEY, algorithm=ALGORITHM)
    return TokenResponse(access_token=token)


def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Decode the JWT and return the subject, or raise 401."""
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user: str | None = payload.get("sub")
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@api_app.get("/api/me")
def me(user: str = Depends(_get_current_user)) -> MeResponse:
    """Return the authenticated user's identity."""
    return MeResponse(user=user)


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------
class AuthState(rx.State):
    """State holding login status and the backend-only current user."""

    is_logged_in: bool = False
    _current_user: str = ""

    async def do_login(self) -> None:
        """Call POST /api/login then GET /api/me and update state."""
        import httpx

        async with httpx.AsyncClient() as client:
            # 1. Login
            login_resp = await client.post(
                "http://localhost:8000/api/login",
                json={"username": "admin", "password": "secret"},
            )
            if login_resp.status_code != 200:
                self.is_logged_in = False
                return
            token = login_resp.json()["access_token"]

            # 2. Verify identity via /api/me
            me_resp = await client.get(
                "http://localhost:8000/api/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me_resp.status_code == 200:
                self.is_logged_in = True
                self._current_user = me_resp.json()["user"]
            else:
                self.is_logged_in = False


# ---------------------------------------------------------------------------
# Reflex page
# ---------------------------------------------------------------------------
def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("JWT Auth Demo", size="7"),
            rx.cond(
                AuthState.is_logged_in,
                rx.text("Logged in: True"),
                rx.text("Logged in: False"),
            ),
            rx.button(
                "Login",
                on_click=AuthState.do_login,
            ),
            spacing="4",
            justify="center",
            min_height="85vh",
        ),
    )


# ---------------------------------------------------------------------------
# Wire FastAPI sub-app into Reflex via api_transformer
# ---------------------------------------------------------------------------
app = rx.App(api_transformer=api_app)
app.add_page(index)