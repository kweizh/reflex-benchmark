"""Reflex + FastAPI application entry point.

Creates a FastAPI app that hosts:
  - Mock OAuth2 provider endpoints   (/auth/authorize, /auth/token)
  - Application PKCE flow endpoints  (/auth/start, /auth/callback)
  - Protected API endpoint           (/api/me)

The FastAPI app is mounted on the Reflex app via ``api_transformer``.
"""

from __future__ import annotations

from fastapi import FastAPI

import reflex as rx

from .api import me
from .flow import callback, start
from .provider import authorize, token
from .state import AppState
from .ui import index

# ── FastAPI app ────────────────────────────────────────────────────────

fastapi_app = FastAPI()

# Mock OAuth provider
fastapi_app.add_api_route(
    "/auth/authorize", authorize, methods=["GET"], response_model=None
)
fastapi_app.add_api_route(
    "/auth/token", token, methods=["POST"], response_model=None
)

# Application PKCE flow
fastapi_app.add_api_route(
    "/auth/start", start, methods=["GET"], response_model=None
)
fastapi_app.add_api_route(
    "/auth/callback", callback, methods=["GET"], response_model=None
)

# Protected API
fastapi_app.add_api_route(
    "/api/me", me, methods=["GET"], response_model=None
)


# ── Reflex app ─────────────────────────────────────────────────────────

app = rx.App(
    api_transformer=fastapi_app,
)

app.add_page(index, route="/", title="OAuth2 PKCE Demo")
