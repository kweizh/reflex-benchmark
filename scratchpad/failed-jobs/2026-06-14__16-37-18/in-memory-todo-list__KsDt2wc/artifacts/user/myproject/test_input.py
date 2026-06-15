import reflex as rx
class State(rx.State):
    new_item: str = ""
def index():
    return rx.input(value=State.new_item, on_change=State.set_new_item)
app = rx.App()
app.add_page(index)
