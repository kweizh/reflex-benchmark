"""Multi-client collaborative drawing board."""

import asyncio
from typing import List

import reflex as rx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ── Database Model ──────────────────────────────────────────────────────────

class Stroke(rx.Model, table=True):
    """A single line segment persisted in SQLite."""
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    color: str = "#000000"
    session_id: str = ""


# ── Pydantic schemas for REST API ──────────────────────────────────────────

class StrokeCreate(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    session_id: str


class StrokeResponse(BaseModel):
    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    session_id: str


# ── Reflex State ────────────────────────────────────────────────────────────

class DrawingState(rx.State):
    """Reactive state that holds all strokes and polls the DB."""
    strokes: List[Stroke] = []

    @rx.event(background=True)
    async def poll_strokes(self):
        """Background task: refresh strokes from DB every ~250 ms."""
        while True:
            async with self:
                with rx.session() as session:
                    rows = session.exec(
                        Stroke.select().order_by(Stroke.id)
                    ).all()
                    self.strokes = list(rows)
            await asyncio.sleep(0.25)


# ── Index Page ──────────────────────────────────────────────────────────────

def stroke_line(stroke: Stroke) -> rx.Component:
    """Render a single stroke as an SVG <line> element."""
    return rx.el.svg.line(
        x1=str(stroke.x1),
        y1=str(stroke.y1),
        x2=str(stroke.x2),
        y2=str(stroke.y2),
        stroke=stroke.color,
        stroke_width="2",
    )


def index() -> rx.Component:
    return rx.el.svg(
        rx.foreach(
            DrawingState.strokes,
            stroke_line,
        ),
        view_box="0 0 800 600",
        width="100%",
        height="100%",
        xmlns="http://www.w3.org/2000/svg",
    )


# ── FastAPI app for REST endpoints ──────────────────────────────────────────

fastapi_app = FastAPI()

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.post("/api/strokes", status_code=201, response_model=StrokeResponse)
def create_stroke(body: StrokeCreate):
    """Create a new stroke and return it."""
    with rx.session() as session:
        stroke = Stroke(
            x1=body.x1,
            y1=body.y1,
            x2=body.x2,
            y2=body.y2,
            color=body.color,
            session_id=body.session_id,
        )
        session.add(stroke)
        session.commit()
        session.refresh(stroke)
        return StrokeResponse(
            id=stroke.id,
            x1=stroke.x1,
            y1=stroke.y1,
            x2=stroke.x2,
            y2=stroke.y2,
            color=stroke.color,
            session_id=stroke.session_id,
        )


@fastapi_app.get("/api/strokes", response_model=List[StrokeResponse])
def list_strokes():
    """Return all strokes in insertion order."""
    with rx.session() as session:
        rows = session.exec(Stroke.select().order_by(Stroke.id)).all()
        return [
            StrokeResponse(
                id=s.id,
                x1=s.x1,
                y1=s.y1,
                x2=s.x2,
                y2=s.y2,
                color=s.color,
                session_id=s.session_id,
            )
            for s in rows
        ]


# ── Reflex App ──────────────────────────────────────────────────────────────

app = rx.App(api_transformer=fastapi_app)
app.add_page(index)