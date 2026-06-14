"""FastAPI router for JWT authentication endpoints."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import jwt

# Fixed credentials and secret (hard-coded as per requirements)
VALID_USERNAME = "alice_h4k9m2"
VALID_PASSWORD = "P@ssw0rd_X9zL2qN8"
JWT_SECRET = "9f3e8a1c4b7d2e5f8a0b3c6d9e2f1a4b7c0d3e6f9a2b5c8d1e4f7a0b3c6d9e2f"


def create_auth_app() -> FastAPI:
    """Create and return a FastAPI app with JWT auth routes."""
    app = FastAPI()

    @app.post("/auth/login")
    async def login(request: Request):
        body = await request.json()
        username = body.get("username")
        password = body.get("password")

        if username != VALID_USERNAME or password != VALID_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = jwt.encode(
            {"sub": username},
            JWT_SECRET,
            algorithm="HS256",
        )
        return JSONResponse(
            content={"access_token": token, "token_type": "bearer"},
            status_code=200,
        )

    @app.get("/auth/me")
    async def me(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")

        token = auth_header[len("Bearer "):]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            username = payload.get("sub")
            if not username:
                raise HTTPException(status_code=401, detail="Invalid token payload")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

        return JSONResponse(
            content={"username": username},
            status_code=200,
        )

    return app
