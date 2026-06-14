"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config
from reflex.components.component import NoSSRComponent


class HexColorPicker(NoSSRComponent):
    """A wrapper for the react-colorful HexColorPicker component."""

    library = "react-colorful"
    tag = "HexColorPicker"

    # The color prop bound to the React component's color prop.
    color: rx.Var[str]

    # Event trigger that forwards the new color string to the Python handler.
    on_change: rx.EventHandler[lambda color: [color]]


class State(rx.State):
    """The app state."""

    hex_color: str = "#000000"

    def set_color(self, color: str):
        """Update the hex color from the picker's on_change event."""
        self.hex_color = color


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Color Picker Demo", size="9"),
            HexColorPicker.create(
                color=State.hex_color,
                on_change=State.set_color,
            ),
            rx.text(
                State.hex_color,
                background_color=State.hex_color,
                padding="1em",
                border_radius="0.5em",
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)