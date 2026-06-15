import reflex as rx

class State(rx.State):
    text: str = ""

def index():
    return rx.input(value=State.text, on_change=State.set_text)

app = rx.App()
app.add_page(index)
