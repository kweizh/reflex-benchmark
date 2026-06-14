import reflex as rx
import numpy as np
from fastapi import FastAPI
import collections.abc

collections.abc.Sequence.register(np.ndarray)

def generate_points() -> np.ndarray:
    x = np.linspace(0, 10, 50)
    y = np.sin(x) + np.random.normal(0, 0.1, 50)
    return np.column_stack((x, y))

@rx.serializer
def serialize_ndarray(arr: np.ndarray) -> list[dict[str, float]]:
    return [{"x": float(row[0]), "y": float(row[1])} for row in arr]

class State(rx.State):
    points: np.ndarray = generate_points()

    def regenerate(self):
        self.points = generate_points()

def index() -> rx.Component:
    return rx.vstack(
        rx.recharts.line_chart(
            rx.recharts.line(data_key="y"),
            rx.recharts.x_axis(data_key="x"),
            data=State.points,
            width="100%",
            height=300,
        ),
        rx.button("Regenerate", on_click=State.regenerate),
    )

fastapi_app = FastAPI()

@fastapi_app.get("/api/points")
def api_points():
    arr = generate_points()
    return serialize_ndarray(arr)

app = rx.App(api_transformer=fastapi_app)
app.add_page(index)
