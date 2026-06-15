"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx
from .react_quill import react_quill


class State(rx.State):
    """The app state."""
    content: str = ""

    def set_content(self, v: str):
        self.content = v


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("React-Quill Rich Text Editor", size="8"),
            react_quill(
                value=State.content,
                on_change=State.set_content,
            ),
            rx.heading("Live HTML Preview", size="6"),
            rx.html(State.content),
            spacing="5",
            align_items="stretch",
            min_height="85vh",
            padding_y="2em",
        ),
    )


app = rx.App()
app.add_page(index)
