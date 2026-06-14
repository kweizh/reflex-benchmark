"""Reflex UI pages."""

from __future__ import annotations

import reflex as rx


def index() -> rx.Component:
    """Home page with a Sign in link that starts the OAuth2 PKCE flow."""
    return rx.container(
        rx.heading("Sign in"),
        rx.link(
            rx.button("Sign in with OAuth2"),
            href="/auth/start",
        ),
    )
