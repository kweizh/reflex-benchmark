import reflex as rx
from rxconfig import config
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import httpx

# Fixed Credentials
USERNAME = "alice_h4k9m2"
PASSWORD = "P@ssw0rd_X9zL2qN8"
SECRET_KEY = "9f3e8a1c4b7d2e5f8a0b3c6d9e2f1a4b7c0d3e6f9a2b5c8d1e4f7a0b3c6d9e2f"
ALGORITHM = "HS256"

# FastAPI Setup
custom_api = FastAPI()
auth_router = APIRouter(prefix="/auth")

class LoginRequest(BaseModel):
    username: str
    password: str

@auth_router.post("/login")
def login(req: LoginRequest):
    if req.username == USERNAME and req.password == PASSWORD:
        token = jwt.encode({"sub": req.username}, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@auth_router.get("/me")
def get_me(REDACTED Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

custom_api.include_router(auth_router)

class State(rx.State):
    """The app state."""
    _access_token: str = ""
    username: str = ""

    async def do_login(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8000/auth/login",
                json={"username": USERNAME, "password": PASSWORD}
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data["access_token"]
                
                # Now fetch me
                me_resp = await client.get(
                    "http://localhost:8000/auth/me",
                    headers={"Authorization": f"Bearer {self._access_token}"}
                )
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    self.username = me_data["username"]

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Secure JWT API Gateway", size="9"),
            rx.button("Login", on_click=State.do_login),
            rx.cond(
                State.username != "",
                rx.text(State.username)
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )

app = rx.App(api_transformer=custom_api)
app.add_page(index)
