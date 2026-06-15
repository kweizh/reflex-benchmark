"""Reflex app with a ReactQuill rich-text editor."""

import reflex as rx

from rxconfig import config
from myproject.react_quill import react_quill


class State(rx.State):
    """Application state."""

    content: str = ""

    def set_content(self, v: str):
        """Update the editor content.

        Args:
            v: The new HTML string from the editor.
        """
        self.content = v


def index() -> rx.Component:
    """The main page: a Quill editor and a live HTML preview below it."""
    return rx.container(
        rx.vstack(
            rx.heading("React-Quill Editor", size="7"),
            react_quill(
                value=State.content,
                on_change=State.set_content,
                width="100%",
            ),
            rx.divider(),
            rx.heading("Live Preview", size="5"),
            rx.html(State.content),
            spacing="4",
            width="100%",
        ),
        padding="4",
        max_width="800px",
    )


app = rx.App()
app.add_page(index)
