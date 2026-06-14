"""Protected API endpoints."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from .credentials import USERNAME
from .provider import get_current_token


async def me(request: Request) -> JSONResponse:
    """Return the demo user identity when a valid Bearer token is provided."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    token = auth_header[len("Bearer "):]
    current_token = get_current_token()

    if current_token is None or token != current_token:
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    return JSONResponse(status_code=200, content={"username": USERNAME})
