import reflex as rx
import sqlmodel
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio

class Stroke(rx.Model, table=True):
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    session_id: str

class State(rx.State):
    strokes: list[Stroke] = []

    @rx.event(background=True)
    async def poll_strokes(self):
        while True:
            async with self:
                with rx.session() as session:
                    self.strokes = session.exec(sqlmodel.select(Stroke)).all()
            await asyncio.sleep(0.25)

def index() -> rx.Component:
    return rx.container(
        rx.el.svg(
            rx.foreach(
                State.strokes,
                lambda s: rx.el.svg.line(
                    x1=s.x1.to(str),
                    y1=s.y1.to(str),
                    x2=s.x2.to(str),
                    y2=s.y2.to(str),
                    stroke=s.color
                )
            ),
            width="100%",
            height="100vh"
        )
    )

fastapi_app = FastAPI()

class StrokeInput(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    session_id: str

@fastapi_app.post("/api/strokes", status_code=201)
def create_stroke(stroke: StrokeInput):
    with rx.session() as session:
        new_stroke = Stroke(**stroke.model_dump())
        session.add(new_stroke)
        session.commit()
        session.refresh(new_stroke)
        return new_stroke

@fastapi_app.get("/api/strokes")
def get_strokes():
    with rx.session() as session:
        return session.exec(sqlmodel.select(Stroke)).all()

app = rx.App(api_transformer=fastapi_app)
app.add_page(index, on_load=State.poll_strokes)
