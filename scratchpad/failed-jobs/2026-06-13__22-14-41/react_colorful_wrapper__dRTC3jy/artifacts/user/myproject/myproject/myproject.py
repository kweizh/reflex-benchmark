"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config

from .color_picker import HexColorPicker


class State(rx.State):
    """The app state."""

    color: str = "#aabbcc"

    def set_color(self, color: str):
        """Set the hex color from the color picker.

        Args:
            color: The new hex color string.
        """
        self.color = color


def index() -> rx.Component:
    """The index page with the color picker."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Color Picker", size="9"),
            HexColorPicker.create(
                color=State.color,
                on_change=State.set_color,
            ),
            rx.text(
                State.color,
                background_color=State.color,
                padding="1em",
                border_radius="0.5em",
                font_weight="bold",
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
