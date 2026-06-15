"""Color picker app using react-colorful wrapped as a Reflex NoSSRComponent."""

import reflex as rx

from reflex.components.component import NoSSRComponent


class ColorPicker(NoSSRComponent):
    """A wrapper around react-colorful's HexColorPicker."""

    library = "react-colorful@5.7.0"
    tag = "HexColorPicker"

    color: rx.Var[str]

    on_change: rx.EventHandler[lambda color: [color]]


color_picker = ColorPicker.create


class State(rx.State):
    """The app state."""

    color: str = "#ff0000"

    def set_color(self, c: str):
        """Set the current color."""
        self.color = c


def index() -> rx.Component:
    """The main page with a color preview and picker."""
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
        padding="4em",
    )


app = rx.App()
app.add_page(index)