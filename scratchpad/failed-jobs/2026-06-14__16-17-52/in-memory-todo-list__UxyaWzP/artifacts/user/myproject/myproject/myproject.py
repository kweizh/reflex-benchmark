"""In-memory Todo List application built with Reflex."""

import reflex as rx


class State(rx.State):
    """The app state."""

    new_item: str = ""
    items: list[str] = []

    def add_item(self):
        """Add the current new_item to the items list and clear new_item."""
        if self.new_item.strip():
            self.items.append(self.new_item)
            self.new_item = ""

    def remove_item(self, index: int):
        """Remove an item from the items list by its integer index."""
        self.items.pop(index)

    @rx.var(cache=True)
    def total(self) -> int:
        """Return the total number of items."""
        return len(self.items)


def render_item(item: str, index: int) -> rx.Component:
    """Render a single todo item with a Remove button."""
    return rx.hstack(
        rx.text(item, flex="1"),
        rx.button(
            "Remove",
            on_click=State.remove_item(index),
        ),
        width="100%",
        align="center",
    )


def index() -> rx.Component:
    """The main index page."""
    return rx.container(
        rx.vstack(
            rx.heading("Todo List", size="7"),
            rx.hstack(
                rx.input(
                    placeholder="Enter a new item...",
                    value=State.new_item,
                    on_change=State.set_new_item,
                    flex="1",
                ),
                rx.button(
                    "Add",
                    on_click=State.add_item,
                ),
                width="100%",
            ),
            rx.foreach(State.items, render_item),
            rx.text("Total: ", State.total),
            spacing="4",
            width="100%",
            max_width="600px",
            margin="0 auto",
            padding_top="40px",
        ),
    )


app = rx.App()
app.add_page(index)
