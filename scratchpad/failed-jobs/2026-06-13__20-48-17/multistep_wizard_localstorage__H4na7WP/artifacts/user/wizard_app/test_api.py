import reflex as rx
from fastapi import FastAPI, APIRouter

router = APIRouter()
@router.get("/api/test")
def test():
    return {"hello": "world"}

def api_transformer(app: FastAPI):
    app.include_router(router)
    return app

app = rx.App(api_transformer=api_transformer)
