"""Secure JWT API Gateway - Reflex app with custom auth API."""

import reflex as rx
import httpx

from rxconfig import config
from secure_jwt_api_gateway.auth_router import router as auth_router

# Create a FastAPI app for the api_transformer
from fastapi import FastAPI

auth_app = FastAPI()
auth_app.include_router(auth_router)


class AuthState(rx.State):
    """State for authentication flow."""

    # Backend-only state var (starts with _) — never sent to the client
    _jwt_token: str = ""
    # Client-visible state var
    username: str = ""

    def login(self):
        """Call /auth/login, store JWT in backend-only var, then call /auth/me."""
        try:
            response = httpx.post(
                "http://localhost:8000/auth/login",
                json={
                    "username": "alice_h4k9m2",
                    "password": "P@ssw0rd_X9zL2qN8",
                },
            )
            if response.status_code == 200:
                data = response.json()
                self._jwt_token = data["access_token"]
                # Now call /auth/me with the stored token
                me_response = httpx.get(
                    "http://localhost:8000/auth/me",
                    headers={"Authorization": f"Bearer {self._jwt_token}"},
                )
                if me_response.status_code == 200:
                    me_data = me_response.json()
                    self.username = me_data["username"]
        except Exception:
            pass


def index() -> rx.Component:
    """The main page with a Login button and username display."""
    return rx.container(
        rx.vstack(
            rx.heading("Secure JWT API Gateway", size="7"),
            rx.cond(
                AuthState.username != "",
                rx.text(f"Authenticated as: {AuthState.username}", size="5"),
            ),
            rx.button(
                "Login",
                on_click=AuthState.login,
                size="3",
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App(api_transformer=auth_app)
app.add_page(index)