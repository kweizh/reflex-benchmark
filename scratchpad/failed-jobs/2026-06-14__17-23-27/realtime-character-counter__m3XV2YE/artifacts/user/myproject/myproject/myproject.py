"""Character & Word Counter — a Reflex app."""

import reflex as rx


class State(rx.State):
    """The app state."""

    content: str = ""

    @rx.var
    def char_count(self) -> int:
        """Return the number of characters in `content`."""
        return len(self.content)

    @rx.var
    def word_count(self) -> int:
        """Return the number of whitespace-separated words in `content`."""
        return len(self.content.split())

    def set_content(self, value: str):
        """Set the content text."""
        self.content = value


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Character & Word Counter", size="7"),
            rx.text_area(
                placeholder="Type something...",
                value=State.content,
                on_change=State.set_content,
                id="content_input",
                width="100%",
                min_height="200px",
            ),
            rx.text(f"Characters: {State.char_count}"),
            rx.text(f"Words: {State.word_count}"),
            spacing="4",
            padding_top="2em",
        ),
    )


app = rx.App()
app.add_page(index)
