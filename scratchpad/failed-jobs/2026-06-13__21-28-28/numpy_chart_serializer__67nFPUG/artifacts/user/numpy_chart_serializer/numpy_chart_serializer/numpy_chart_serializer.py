"""Reflex app: numpy ndarray serializer powering a Recharts line chart."""

from __future__ import annotations

import numpy

import reflex as rx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from rxconfig import config


# ---------------------------------------------------------------------------
# Noisy-sine generator (shared by state & API route)
# ---------------------------------------------------------------------------

def generate_noisy_sine(n: int = 50) -> numpy.ndarray:
    """Return an (n, 2) ndarray: column 0 = x, column 1 = sin(x) + noise."""
    x = numpy.linspace(0, 4 * numpy.pi, n)
    noise = numpy.random.normal(0, 0.2, size=n)
    y = numpy.sin(x) + noise
    return numpy.column_stack((x, y))


# ---------------------------------------------------------------------------
# Custom serializer so Reflex can JSON-encode numpy.ndarray
# ---------------------------------------------------------------------------

@rx.serializer
def serialize_ndarray(arr: numpy.ndarray) -> list[dict[str, float]]:
    """Convert an (N, 2) ndarray into a list of {"x": float, "y": float}."""
    return [{"x": float(row[0]), "y": float(row[1])} for row in arr]


# ---------------------------------------------------------------------------
# Reflex state
# ---------------------------------------------------------------------------

class ChartState(rx.State):
    """State holding the chart data as a typed numpy.ndarray."""

    points: numpy.ndarray = generate_noisy_sine()

    def regenerate(self) -> None:
        """Replace points with a fresh noisy sine wave."""
        self.points = generate_noisy_sine()


# ---------------------------------------------------------------------------
# UI page
# ---------------------------------------------------------------------------

def index() -> rx.Component:
    # Use _replace to declare the serialized type for the prop type check.
    # The serializer handles actual runtime conversion; _var_type tells
    # the compiler what shape the frontend will see.
    chart_data = ChartState.points._replace(
        _var_type=list[dict[str, float]],
    )

    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("NumPy → Recharts", size="9"),
            rx.recharts.line_chart(
                rx.recharts.line(
                    data_key="y",
                    stroke="#8884d8",
                    stroke_width=2,
                    dot=False,
                ),
                rx.recharts.x_axis(data_key="x"),
                rx.recharts.y_axis(),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                rx.recharts.tooltip(),
                data=chart_data,
                width="100%",
                height=400,
            ),
            rx.button(
                "Regenerate",
                on_click=ChartState.regenerate,
                margin_top="1rem",
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


# ---------------------------------------------------------------------------
# FastAPI custom route (same generator, fresh random data each call)
# ---------------------------------------------------------------------------

fastapi_app = FastAPI()


@fastapi_app.get("/api/points")
def api_points() -> JSONResponse:
    arr = generate_noisy_sine()
    data = serialize_ndarray(arr)
    return JSONResponse(content=data)


# ---------------------------------------------------------------------------
# Reflex app
# ---------------------------------------------------------------------------

app = rx.App(api_transformer=fastapi_app)
app.add_page(index, route="/", title="NumPy Chart Serializer")