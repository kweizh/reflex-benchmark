"""Reflex application with OAuth2 PKCE login flow."""

import reflex as rx

from .auth import fastapi_app


# ── State ──────────────────────────────────────────────────────────

class AuthState(rx.State):
    """Application state holding the access token.

    * ``access_token`` is a client-side cookie (synced to/from the browser).
    * ``_access_token`` is a backend-only mirror for use in server-side requests.
    """

    access_token: str = rx.Cookie("")
    _access_token: str = ""

    def on_load(self) -> None:
        """Mirror the cookie value into the backend-only var."""
        self._access_token = self.access_token


# ── Page ───────────────────────────────────────────────────────────

def index() -> rx.Component:
    """Home page with a Sign-in link."""
    return rx.container(
        rx.vstack(
            rx.heading("Sign in", size="5"),
            rx.link(
                rx.button("Sign in"),
                href="/auth/start",
            ),
            spacing="4",
            align="center",
            padding_top="4em",
        ),
    )


# ── App ────────────────────────────────────────────────────────────

app = rx.App(api_transformer=fastapi_app)
app.add_page(index, route="/", on_load=AuthState.on_load)