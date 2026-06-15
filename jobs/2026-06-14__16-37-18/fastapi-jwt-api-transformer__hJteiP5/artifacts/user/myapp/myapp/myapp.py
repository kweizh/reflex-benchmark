import reflex as rx
from fastapi import FastAPI
import httpx
import secrets
import jwt
from pydantic import BaseModel

SECRET_KEY = secrets.token_urlsafe(32)

fastapi_app = FastAPI()

class LoginRequest(BaseModel):
    username: str
    password: str

@fastapi_app.post("/api/login")
def login(req: LoginRequest):
    if req.username == "admin" and req.password == "secret":
        token = jwt.encode({"sub": req.username}, SECRET_KEY, algorithm="HS256")
        return {"access_token": token}
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid credentials")

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@fastapi_app.get("/api/me")
def me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {"user": payload.get("sub")}
    except jwt.PyJWTError:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")

class AuthState(rx.State):
    is_logged_in: bool = False
    _current_user: str = ""

    async def do_login(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post("http://localhost:8000/api/login", json={"username": "admin", "password": "secret"})
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                resp_me = await client.get("http://localhost:8000/api/me", headers={"Authorization": f"Bearer {token}"})
                if resp_me.status_code == 200:
                    self._current_user = resp_me.json().get("user")
                    self.is_logged_in = True

def index() -> rx.Component:
    return rx.container(
        rx.text(f"Logged in: {AuthState.is_logged_in}"),
        rx.button("Login", on_click=AuthState.do_login)
    )

app = rx.App(api_transformer=fastapi_app)
app.add_page(index)
