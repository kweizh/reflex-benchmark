import reflex as rx
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import jwt
import httpx
from typing import Optional

# Fixed credentials and secret
USERNAME = "alice_h4k9m2"
PASSWORD = "P@ssw0rd_X9zL2qN8"
JWT_SECRET = "9f3e8a1c4b7d2e5f8a0b3c6d9e2f1a4b7c0d3e6f9a2b5c8d1e4f7a0b3c6d9e2f"
ALGORITHM = "HS256"

# API Models
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserMeResponse(BaseModel):
    username: str

# FastAPI Router
router = APIRouter(prefix="/auth")

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    if req.username == USERNAME and req.password == PASSWORD:
        payload = {"sub": req.username}
        token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/me", response_model=UserMeResponse)
async def me(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return UserMeResponse(username=payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Reflex State
class State(rx.State):
    authenticated_username: str = ""
    # Backend-only state var (starts with underscore)
    _jwt_token: str = ""

    async def handle_login(self):
        async with httpx.AsyncClient() as client:
            # Login call
            try:
                login_resp = await client.post(
                    "http://localhost:8000/auth/login",
                    json={"username": USERNAME, "password": PASSWORD}
                )
                if login_resp.status_code == 200:
                    data = login_resp.json()
                    self._jwt_token = data["access_token"]
                    
                    # Call /auth/me using the token
                    me_resp = await client.get(
                        "http://localhost:8000/auth/me",
                        headers={"Authorization": f"Bearer {self._jwt_token}"}
                    )
                    if me_resp.status_code == 200:
                        me_data = me_resp.json()
                        self.authenticated_username = me_data["username"]
            except Exception as e:
                print(f"Error during login flow: {e}")

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Secure JWT API Gateway", size="7"),
            rx.button("Login", on_click=State.handle_login),
            rx.cond(
                State.authenticated_username != "",
                rx.text(f"Logged in as: {State.authenticated_username}", id="username-display"),
                rx.text("Not logged in"),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )

def api_transformer(app: FastAPI) -> FastAPI:
    custom_api = FastAPI()
    custom_api.include_router(router)
    app.mount("/", custom_api)
    return app

app = rx.App(api_transformer=api_transformer)
app.add_page(index)
