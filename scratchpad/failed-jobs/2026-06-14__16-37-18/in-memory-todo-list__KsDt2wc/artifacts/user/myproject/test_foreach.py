import reflex as rx
class State(rx.State):
    items: list[str] = ["a", "b"]
    def remove_item(self, index: int):
        self.items.pop(index)

def render_item(item: rx.Var[str], index: int) -> rx.Component:
    return rx.hstack(
        rx.text(item),
        rx.button("Remove", on_click=lambda: State.remove_item(index))
    )

def index() -> rx.Component:
    return rx.foreach(State.items, render_item)

app = rx.App()
app.add_page(index)
