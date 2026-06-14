"""Secure JWT API Gateway - Reflex app with JWT authentication."""

import reflex as rx
import httpx

from .auth import create_auth_app


class State(rx.State):
    """The app state."""

    # Backend-only state var (starts with underscore, never sent to client)
    _access_token: str = ""

    # Client-visible state var for the authenticated username
    username: str = ""

    @rx.event
    async def login(self):
        """Login flow: call /auth/login, store JWT, then call /auth/me."""
        async with httpx.AsyncClient() as client:
            # Step 1: Login to get JWT
            login_resp = await client.post(
                "http://localhost:8000/auth/login",
                json={"username": "alice_h4k9m2", "password": "P@ssw0rd_X9zL2qN8"},
            )
            if login_resp.status_code != 200:
                return

            login_data = login_resp.json()
            token = login_data["access_token"]

            # Store token in backend-only var (never serialized to client)
            self._access_token = token

            # Step 2: Use token to get identity
            me_resp = await client.get(
                "http://localhost:8000/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me_resp.status_code != 200:
                return

            me_data = me_resp.json()
            self.username = me_data["username"]


def index() -> rx.Component:
    """Root page with Login button and username display."""
    return rx.container(
        rx.vstack(
            rx.heading("Secure JWT API Gateway", size="8"),
            rx.button(
                "Login",
                on_click=State.login,
            ),
            rx.cond(
                State.username != "",
                rx.text(f"Authenticated as: {State.username}", color="green"),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


# Create the FastAPI auth app for api_transformer
auth_app = create_auth_app()

app = rx.App(api_transformer=auth_app)
app.add_page(index)
