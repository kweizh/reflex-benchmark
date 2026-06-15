import reflex as rx
from fastapi import FastAPI

fastapi_app = FastAPI()

@fastapi_app.get("/hello")
def hello():
    return {"hello": "world"}

app = rx.App(api_transformer=fastapi_app)
