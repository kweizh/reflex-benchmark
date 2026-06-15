"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel
import httpx
import reflex as rx

# Generate JWT secret key at application startup
# DO NOT read from os.environ, DO NOT hardcode as a literal constant
JWT_SECRET = secrets.token_urlsafe(32)

# Create FastAPI instance
fastapi_app = FastAPI()

class LoginRequest(BaseModel):
    username: str
    password: str

@fastapi_app.post("/api/login")
def login(req: LoginRequest):
    if req.username == "admin" and req.password == "secret":
        token = jwt.encode({"sub": "admin"}, JWT_SECRET, algorithm="HS256")
        return {"access_token": token}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )

security = HTTPBearer()

@fastapi_app.get("/api/me")
def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("sub") == "admin":
            return {"user": "admin"}
    except jwt.PyJWTError:
        pass
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token"
    )


class AuthState(rx.State):
    # Frontend state variables
    is_logged_in: bool = False
    username_input: str = "admin"
    password_input: str = "secret"
    login_error: str = ""
    
    # Backend-only state variable
    _current_user: str = ""

    def set_username_input(self, username_input: str):
        self.username_input = username_input

    def set_password_input(self, password_input: str):
        self.password_input = password_input

    async def handle_login(self):
        self.login_error = ""
        async with httpx.AsyncClient() as client:
            try:
                # 1. Call POST /api/login
                login_resp = await client.post(
                    "http://localhost:8000/api/login",
                    json={
                        "username": self.username_input,
                        "password": self.password_input
                    }
                )
                if login_resp.status_code != 200:
                    self.is_logged_in = False
                    self._current_user = ""
                    self.login_error = "Invalid credentials"
                    return
                
                token_data = login_resp.json()
                token = token_data.get("access_token")
                
                # 2. Call GET /api/me
                me_resp = await client.get(
                    "http://localhost:8000/api/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if me_resp.status_code != 200:
                    self.is_logged_in = False
                    self._current_user = ""
                    self.login_error = "Failed to fetch user info"
                    return
                
                user_data = me_resp.json()
                self._current_user = user_data.get("user", "")
                self.is_logged_in = True
            except Exception as e:
                self.login_error = f"Error during auth: {str(e)}"
                self.is_logged_in = False
                self._current_user = ""

    def handle_logout(self):
        self.is_logged_in = False
        self._current_user = ""
        self.username_input = "admin"
        self.password_input = "secret"
        self.login_error = ""


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Reflex JWT Auth App", size="8"),
            
            # Show login status based on the frontend state var
            rx.vstack(
                rx.text("is_logged_in: ", AuthState.is_logged_in.to_string(), size="4", weight="bold"),
                rx.cond(
                    AuthState.is_logged_in,
                    rx.text("Status: Logged In successfully!", color="green"),
                    rx.text("Status: Logged Out / Unauthenticated", color="red")
                ),
                spacing="2",
                align="center",
            ),
            
            rx.divider(),
            
            # Form to perform login
            rx.cond(
                ~AuthState.is_logged_in,
                rx.vstack(
                    rx.text("Login Form", size="5", weight="bold"),
                    rx.input(
                        placeholder="Username",
                        value=AuthState.username_input,
                        on_change=AuthState.set_username_input,
                        width="300px",
                    ),
                    rx.input(
                        placeholder="Password",
                        type="password",
                        value=AuthState.password_input,
                        on_change=AuthState.set_password_input,
                        width="300px",
                    ),
                    rx.button("Log In", on_click=AuthState.handle_login, width="300px"),
                    rx.cond(
                        AuthState.login_error != "",
                        rx.text(AuthState.login_error, color="red"),
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.vstack(
                    rx.text("Welcome back, Admin!", size="5", weight="bold"),
                    rx.button("Log Out", on_click=AuthState.handle_logout, width="300px"),
                    spacing="3",
                    align="center",
                )
            ),
            
            spacing="5",
            justify="center",
            min_height="85vh",
            align="center",
        ),
    )


# Wire the FastAPI instance into Reflex with api_transformer
app = rx.App(api_transformer=fastapi_app)
app.add_page(index)
