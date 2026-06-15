"""Real-Time Character & Word Counter built with Reflex."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    content: str = ""

    def set_content(self, value: str) -> None:
        """Update content as the user types."""
        self.content = value

    @rx.var(cache=True)
    def char_count(self) -> int:
        """Return the number of characters in content."""
        return len(self.content)

    @rx.var(cache=True)
    def word_count(self) -> int:
        """Return the number of whitespace-separated words in content."""
        return len(self.content.split())


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Real-Time Character & Word Counter", size="7"),
            rx.text_area(
                id="content_input",
                value=State.content,
                on_change=State.set_content,
                placeholder="Start typing here…",
                width="100%",
                rows="8",
            ),
            rx.text(f"Characters: {State.char_count}"),
            rx.text(f"Words: {State.word_count}"),
            spacing="4",
            width="100%",
            max_width="600px",
            padding="2em",
        ),
        padding_top="4em",
    )


app = rx.App()
app.add_page(index)
