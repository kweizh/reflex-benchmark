import reflex as rx

class State(rx.State):
    """The app state."""
    content: str = ""

    def set_content(self, value: str):
        self.content = value

    @rx.var(cache=True)
    def char_count(self) -> int:
        return len(self.content)

    @rx.var(cache=True)
    def word_count(self) -> int:
        return len(self.content.split())

def index() -> rx.Component:
    return rx.container(
        rx.text_area(
            id="content_input",
            value=State.content,
            on_change=State.set_content,
        ),
        rx.text(f"Characters: {State.char_count}"),
        rx.text(f"Words: {State.word_count}")
    )

app = rx.App()
app.add_page(index)
