import reflex as rx
from typing import List
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel

# 1. Stroke Model
class Stroke(rx.Model, table=True):
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    session_id: str

# 2. Reactive State
class State(rx.State):
    strokes: List[Stroke] = []

    @rx.event(background=True)
    async def refresh_strokes(self):
        while True:
            async with self:
                with rx.session() as session:
                    self.strokes = session.exec(
                        Stroke.select().order_by(Stroke.id)
                    ).all()
            await asyncio.sleep(0.25)

    def on_load(self):
        return State.refresh_strokes

# 3. REST API setup
api_app = FastAPI()

class StrokeCreate(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    session_id: str

@api_app.post("/strokes", status_code=201)
async def create_stroke(stroke_data: StrokeCreate):
    with rx.session() as session:
        db_stroke = Stroke(
            x1=stroke_data.x1,
            y1=stroke_data.y1,
            x2=stroke_data.x2,
            y2=stroke_data.y2,
            color=stroke_data.color,
            session_id=stroke_data.session_id
        )
        session.add(db_stroke)
        session.commit()
        session.refresh(db_stroke)
        return {
            "id": db_stroke.id,
            "x1": db_stroke.x1,
            "y1": db_stroke.y1,
            "x2": db_stroke.x2,
            "y2": db_stroke.y2,
            "color": db_stroke.color,
            "session_id": db_stroke.session_id
        }

@api_app.get("/strokes")
async def list_strokes():
    with rx.session() as session:
        strokes = session.exec(Stroke.select().order_by(Stroke.id)).all()
        return [
            {
                "id": s.id,
                "x1": s.x1,
                "y1": s.y1,
                "x2": s.x2,
                "y2": s.y2,
                "color": s.color,
                "session_id": s.session_id
            } for s in strokes
        ]

def api_transformer(app: FastAPI):
    app.mount("/api", api_app)
    return app

# 4. Index Page
def index() -> rx.Component:
    return rx.center(
        rx.el.svg(
            rx.foreach(
                State.strokes,
                lambda stroke: rx.el.svg.line(
                    x1=stroke.x1.to_string(),
                    y1=stroke.y1.to_string(),
                    x2=stroke.x2.to_string(),
                    y2=stroke.y2.to_string(),
                    stroke=stroke.color,
                    stroke_width="2",
                )
            ),
            width="800px",
            height="600px",
            border="1px solid black",
        ),
        padding="2em",
    )

app = rx.App(api_transformer=api_transformer)
app.add_page(index, on_load=State.on_load)
