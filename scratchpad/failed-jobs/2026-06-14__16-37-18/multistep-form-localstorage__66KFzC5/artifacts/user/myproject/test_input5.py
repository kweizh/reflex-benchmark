import reflex as rx

class State(rx.State):
    email: str = ""

def index():
    return rx.input(value=State.email, on_change=State.set_email)

app = rx.App()
app.add_page(index)
