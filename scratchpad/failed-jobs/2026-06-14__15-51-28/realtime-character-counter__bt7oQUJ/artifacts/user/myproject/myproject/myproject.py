"""Real-Time Character & Word Counter app."""

import reflex as rx


class State(rx.State):
    content: str = ""

    def set_content(self, text: str):
        self.content = text

    @rx.var(cache=True)
    def char_count(self) -> int:
        return len(self.content)

    @rx.var(cache=True)
    def word_count(self) -> int:
        return len(self.content.split())


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Real-Time Character & Word Counter", size="6"),
            rx.text_area(
                id="content_input",
                value=State.content,
                on_change=State.set_content,
                placeholder="Type your text here...",
                width="100%",
                height="200px",
            ),
            rx.text(f"Characters: {State.char_count}"),
            rx.text(f"Words: {State.word_count}"),
            spacing="4",
            padding="2em",
            width="100%",
            max_width="600px",
        ),
        width="100vw",
        height="100vh",
    )


app = rx.App()
app.add_page(index)
