"""Real-Time Character & Word Counter."""

import reflex as rx


class State(rx.State):
    """The app state, holding the text content and derived counters."""

    content: str = ""

    @rx.var
    def char_count(self) -> int:
        """Return the number of characters in content."""
        return len(self.content)

    @rx.var
    def word_count(self) -> int:
        """Return the number of whitespace-separated words in content."""
        return len(self.content.split())

    def set_content(self, value: str):
        """Set the content var."""
        self.content = value


def index() -> rx.Component:
    """The main page with a textarea and live counters."""
    return rx.container(
        rx.vstack(
            rx.heading("Character & Word Counter", size="7"),
            rx.text_area(
                id="content_input",
                value=State.content,
                on_change=State.set_content,
                placeholder="Type something here...",
                width="100%",
                min_height="200px",
            ),
            rx.text(f"Characters: {State.char_count}"),
            rx.text(f"Words: {State.word_count}"),
            spacing="4",
            align="stretch",
            padding_top="2em",
        ),
    )


app = rx.App()
app.add_page(index)