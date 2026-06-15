"""Reflex app wrapping react-colorful's HexColorPicker."""

import reflex as rx
from reflex.components.component import NoSSRComponent

from rxconfig import config


class ColorPicker(NoSSRComponent):
    """A color picker component wrapping react-colorful's HexColorPicker."""

    library: str = "react-colorful@5.7.0"
    tag: str = "HexColorPicker"

    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]


color_picker = ColorPicker.create


class State(rx.State):
    """The app state."""

    color: str = "#ff0000"

    def set_color(self, c: str):
        self.color = c


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.box(
                width="80px",
                height="80px",
                background=State.color,
            ),
            color_picker(
                color=State.color,
                on_change=State.set_color,
            ),
            spacing="4",
            align="center",
        ),
        min_height="100vh",
    )


app = rx.App()
app.add_page(index)
