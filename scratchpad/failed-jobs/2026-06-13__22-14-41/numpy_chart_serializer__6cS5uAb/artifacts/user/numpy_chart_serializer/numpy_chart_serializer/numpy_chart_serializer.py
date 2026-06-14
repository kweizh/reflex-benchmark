"""Reflex app with numpy ndarray serializer powering a Recharts line chart."""

import numpy as np
import reflex as rx
from fastapi import FastAPI
from fastapi.responses import JSONResponse


# ── Noisy sine-wave generator ────────────────────────────────────────────────

def generate_noisy_sine(n_points: int = 50) -> np.ndarray:
    """Generate a (n_points, 2) array of noisy sine-wave points.

    Column 0 is x (evenly spaced), column 1 is y = sin(x) + small noise.
    Each call produces a genuinely different array thanks to numpy.random.
    """
    x = np.linspace(0, 4 * np.pi, n_points)
    noise = np.random.normal(scale=0.15, size=n_points)
    y = np.sin(x) + noise
    return np.column_stack((x, y))


# ── Serializer: numpy.ndarray → list[dict[str, float]] ─────────────────────

@rx.serializer(to=list[dict[str, float]])
def serialize_ndarray(arr: np.ndarray) -> list[dict[str, float]]:
    """Convert a (N, 2) ndarray into a list of {"x": float, "y": float} dicts."""
    return [{"x": float(row[0]), "y": float(row[1])} for row in arr]


# ── FastAPI sub-app for the custom REST route ──────────────────────────────

api_app = FastAPI()


@api_app.get("/api/points")
def api_points():
    """Return a fresh array of 50 noisy sine-wave points as JSON."""
    arr = generate_noisy_sine(50)
    data = serialize_ndarray(arr)
    return JSONResponse(content=data)


# ── Reflex State ────────────────────────────────────────────────────────────

class State(rx.State):
    """Application state holding the ndarray points."""

    points: np.ndarray = generate_noisy_sine(50)

    def regenerate(self):
        """Replace `points` with a fresh noisy sine-wave array."""
        self.points = generate_noisy_sine(50)


# ── UI ──────────────────────────────────────────────────────────────────────

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("NumPy Line Chart", size="8"),
            rx.recharts.line_chart(
                rx.recharts.line(data_key="y"),
                rx.recharts.x_axis(data_key="x"),
                data=State.points,
                width="100%",
                height=400,
            ),
            rx.button("Regenerate", on_click=State.regenerate),
            spacing="6",
            align="center",
            padding_top="2em",
        ),
    )


# ── App ─────────────────────────────────────────────────────────────────────

app = rx.App(api_transformer=api_app)
app.add_page(index)
