"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config
from myproject.react_quill import react_quill


class State(rx.State):
    """The app state."""

    content: str = ""

    def set_content(self, v: str):
        """Set the content from the editor."""
        self.content = v


def index() -> rx.Component:
    """The main page with the Quill editor and live HTML preview."""
    return rx.container(
        rx.vstack(
            rx.heading("React Quill Editor", size="7"),
            react_quill(
                value=State.content,
                on_change=State.set_content,
            ),
            rx.divider(),
            rx.heading("Live HTML Preview", size="5"),
            rx.html(State.content),
            spacing="3",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)