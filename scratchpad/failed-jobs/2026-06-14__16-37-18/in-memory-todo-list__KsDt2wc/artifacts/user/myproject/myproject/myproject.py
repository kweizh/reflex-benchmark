import reflex as rx

class State(rx.State):
    """The app state."""
    new_item: str = ""
    items: list[str] = []

    def set_new_item(self, value: str):
        self.new_item = value

    def add_item(self):
        if self.new_item.strip():
            self.items.append(self.new_item)
            self.new_item = ""
            
    def remove_item(self, index: int):
        self.items.pop(index)

    @rx.var(cache=True)
    def total(self) -> int:
        return len(self.items)

def render_item(item: rx.Var[str], index: int) -> rx.Component:
    return rx.hstack(
        rx.text(item),
        rx.button("Remove", on_click=lambda: State.remove_item(index))
    )

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Todo List"),
            rx.hstack(
                rx.input(value=State.new_item, on_change=State.set_new_item),
                rx.button("Add", on_click=State.add_item)
            ),
            rx.vstack(
                rx.foreach(State.items, render_item)
            ),
            rx.text("Total: ", State.total),
            spacing="5",
        )
    )

app = rx.App()
app.add_page(index)
