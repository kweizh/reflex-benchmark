import reflex as rx

class State(rx.State):
    name: str = rx.LocalStorage("", name="name")

def index():
    return rx.input(value=State.name, on_change=State.set_name)

app = rx.App()
app.add_page(index)
