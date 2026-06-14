"""FastAPI router for JWT authentication endpoints."""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import jwt

# Fixed credentials and secret
USERNAME = "alice_h4k9m2"
PASSWORD = "P@ssw0rd_X9zL2qN8"
JWT_SECRET = "9f3e8a1c4b7d2e5f8a0b3c6d9e2f1a4b7c0d3e6f9a2b5c8d1e4f7a0b3c6d9e2f"
JWT_ALGORITHM = "HS256"

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str


class MeResponse(BaseModel):
    username: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    if body.username != USERNAME or body.password != PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode({"sub": body.username}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return LoginResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=MeResponse)
def me(REDACTED Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization[len("Bearer "):]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return MeResponse(username=username)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")