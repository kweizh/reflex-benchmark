import reflex as rx


class State(rx.State):
    new_item: str = ""
    items: list[str] = []

    @rx.var(cache=True)
    def total(self) -> int:
        return len(self.items)

    def set_new_item(self, new_item: str):
        self.new_item = new_item

    def add_item(self):
        self.items.append(self.new_item)
        self.new_item = ""

    def remove_item(self, index: int):
        self.items.pop(index)


def render_item(item, index):
    return rx.hstack(
        rx.text(item),
        rx.button("Remove", on_click=lambda: State.remove_item(index)),
        spacing="3",
        align="center",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("In-Memory Todo List App", size="8"),
            rx.hstack(
                rx.input(
                    value=State.new_item,
                    on_change=State.set_new_item,
                    placeholder="Enter a new todo item...",
                ),
                rx.button("Add", on_click=State.add_item),
                spacing="3",
            ),
            rx.vstack(
                rx.foreach(State.items, render_item),
                spacing="2",
            ),
            rx.text("Total: ", State.total),
            spacing="5",
            align="center",
            margin_top="5em",
        )
    )


app = rx.App()
app.add_page(index)
