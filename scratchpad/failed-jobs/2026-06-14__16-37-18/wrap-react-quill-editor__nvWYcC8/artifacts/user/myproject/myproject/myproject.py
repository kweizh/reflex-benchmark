import reflex as rx
from rxconfig import config
from .react_quill import react_quill

class State(rx.State):
    content: str = ""

    def set_content(self, v: str):
        self.content = v

def index() -> rx.Component:
    return rx.container(
        react_quill(
            value=State.content,
            on_change=State.set_content,
        ),
        rx.html(State.content)
    )

app = rx.App()
app.add_page(index)
