import reflex as rx
from fastapi import FastAPI, Request

api = FastAPI()

@api.post("/submit")
async def submit(request: Request):
    return {"id": 1}

def api_transformer(app):
    app.mount("/api/wizard", api)
    return app

app = rx.App(api_transformer=api_transformer)
app()
