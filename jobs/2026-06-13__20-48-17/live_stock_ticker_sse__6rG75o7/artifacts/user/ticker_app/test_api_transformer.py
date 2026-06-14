import reflex as rx
from fastapi import FastAPI

api_app = FastAPI()

app = rx.App(api_transformer=api_app)
print("Success")
