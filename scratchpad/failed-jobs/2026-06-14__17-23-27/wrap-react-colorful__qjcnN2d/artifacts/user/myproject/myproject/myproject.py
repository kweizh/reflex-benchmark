"""Welcome to Reflex! This file wraps react-colorful's HexColorPicker as a NoSSRComponent."""

import reflex as rx
from reflex.components.component import NoSSRComponent

from rxconfig import config


class ColorPicker(NoSSRComponent):
    """A Reflex wrapper for the react-colorful HexColorPicker component."""

    library = "react-colorful@5.7.0"
    tag = "HexColorPicker"

    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]


color_picker = ColorPicker.create


class State(rx.State):
    """The app state."""

    color: str = "#ff0000"

    def set_color(self, c: str):
        """Update the current color.

        Args:
            c: The new hex color string.
        """
        self.color = c


def index() -> rx.Component:
    """The index page with a color preview and color picker."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Color Picker Demo", size="7"),
            rx.box(
                width="80px",
                height="80px",
                background=State.color,
                border_radius="8px",
                border="2px solid #ccc",
            ),
            color_picker(
                color=State.color,
                on_change=State.set_color,
            ),
            rx.text("Selected: ", State.color, size="3"),
            spacing="5",
            justify="center",
            align="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
