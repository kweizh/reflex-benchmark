"""Multi-client collaborative drawing board application."""

import asyncio
import json

import reflex as rx
import sqlmodel
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class Stroke(rx.Model, table=True):
    """A single stroke segment in the drawing board."""

    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    session_id: str


class State(rx.State):
    """Reactive page state holding the list of strokes."""

    strokes: list[Stroke] = []

    @rx.event(background=True)
    async def poll_strokes(self):
        """Background task that refreshes strokes from the database."""
        while True:
            await asyncio.sleep(0.25)
            async with self:
                with rx.session() as session:
                    self.strokes = session.exec(
                        sqlmodel.select(Stroke).order_by(Stroke.id)
                    ).all()


def index() -> rx.Component:
    """Render the collaborative drawing board."""
    return rx.el.svg(
        rx.foreach(
            State.strokes,
            lambda stroke: rx.el.svg.line(
                x1=stroke.x1,
                y1=stroke.y1,
                x2=stroke.x2,
                y2=stroke.y2,
                stroke=stroke.color,
                stroke_width="3",
            ),
        ),
        width="800",
        height="600",
        style={"border": "1px solid #ccc", "background": "#fff"},
    )


# --- REST API as a Starlette app mounted via api_transformer ---

api_app = Starlette()


@api_app.route("/ping", methods=["GET"])
async def ping(request: Request) -> Response:
    """Health check endpoint."""
    return Response(content=b'"pong"', media_type="application/json")


async def _get_strokes_from_db():
    """Read all strokes from the database in insertion order."""
    with rx.session() as session:
        strokes = session.exec(
            sqlmodel.select(Stroke).order_by(Stroke.id)
        ).all()
        return [
            {
                "id": s.id,
                "x1": s.x1,
                "y1": s.y1,
                "x2": s.x2,
                "y2": s.y2,
                "color": s.color,
                "session_id": s.session_id,
            }
            for s in strokes
        ]


@api_app.route("/api/strokes", methods=["GET"])
async def list_strokes(request: Request) -> JSONResponse:
    """List all strokes."""
    strokes = await _get_strokes_from_db()
    return JSONResponse(content=strokes, status_code=200)


@api_app.route("/api/strokes", methods=["POST"])
async def create_stroke(request: Request) -> JSONResponse:
    """Create a new stroke segment."""
    body = await request.json()
    with rx.session() as session:
        stroke = Stroke(
            x1=body["x1"],
            y1=body["y1"],
            x2=body["x2"],
            y2=body["y2"],
            color=body["color"],
            session_id=body["session_id"],
        )
        session.add(stroke)
        session.commit()
        session.refresh(stroke)
        result = {
            "id": stroke.id,
            "x1": stroke.x1,
            "y1": stroke.y1,
            "x2": stroke.x2,
            "y2": stroke.y2,
            "color": stroke.color,
            "session_id": stroke.session_id,
        }
    return JSONResponse(content=result, status_code=201)


app = rx.App(api_transformer=api_app)
app.add_page(index, route="/", on_load=State.poll_strokes)
