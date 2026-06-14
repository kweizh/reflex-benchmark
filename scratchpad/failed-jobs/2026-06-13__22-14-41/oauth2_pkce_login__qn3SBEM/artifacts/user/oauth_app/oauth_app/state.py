"""Reflex application state."""

from __future__ import annotations

import reflex as rx


class AppState(rx.State):
    """Application state with cookie-synced and backend-only token storage."""

    # Cookie-synced field – mirrored to/from the browser cookie "access_token"
    access_token: rx.Cookie = rx.Cookie(name="access_token", path="/")

    # Backend-only mirror – starts with "_" so it is never sent to the client
    _token: str = ""
