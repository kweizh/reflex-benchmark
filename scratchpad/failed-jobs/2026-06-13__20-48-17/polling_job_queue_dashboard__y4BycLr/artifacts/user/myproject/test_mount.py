from starlette.applications import Starlette
from fastapi import FastAPI
star = Starlette()
fast = FastAPI()
star.mount("/api", fast)
print("Mounted")
