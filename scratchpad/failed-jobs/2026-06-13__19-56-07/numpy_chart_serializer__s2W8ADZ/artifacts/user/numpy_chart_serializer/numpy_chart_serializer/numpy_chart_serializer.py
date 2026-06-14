import reflex as rx
import numpy
from fastapi import FastAPI
from typing import List, Dict

def generate_noisy_sine() -> numpy.ndarray:
    """Generate 50 noisy sine wave points.
    Returns:
        numpy.ndarray of shape (50, 2) where col 0 is x and col 1 is y.
    """
    x = numpy.linspace(0, 10, 50)
    noise = numpy.random.normal(0, 0.1, 50)
    y = numpy.sin(x) + noise
    return numpy.column_stack((x, y))

@rx.serializer
def serialize_ndarray(arr: numpy.ndarray) -> List[Dict[str, float]]:
    """Convert numpy array to a list of dicts for Recharts."""
    return [{"x": float(row[0]), "y": float(row[1])} for row in arr]

class State(rx.State):
    # The state must keep the data as a typed numpy.ndarray of shape (50, 2)
    points: numpy.ndarray = generate_noisy_sine()

    def regenerate(self):
        self.points = generate_noisy_sine()

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Numpy Chart Serializer", size="9"),
            rx.recharts.line_chart(
                rx.recharts.line(
                    data_key="y",
                ),
                rx.recharts.x_axis(data_key="x"),
                rx.recharts.y_axis(),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                rx.recharts.tooltip(),
                data=State.points, # Bound directly to the typed ndarray var
                width="100%",
                height=400,
            ),
            rx.button("Regenerate", on_click=State.regenerate),
            align="center",
            width="80%",
        ),
        height="100vh",
    )

# Build a FastAPI() instance
fastapi_app = FastAPI()

@fastapi_app.get("/api/points")
def get_points():
    points = generate_noisy_sine()
    return serialize_ndarray(points)

# Pass it to rx.App(api_transformer=fastapi_app)
app = rx.App(api_transformer=fastapi_app)
app.add_page(index)
