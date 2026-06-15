"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx


class State(rx.State):
    """The app state."""

    new_item: str = ""
    items: list[str] = []

    @rx.var(cache=True)
    def total(self) -> int:
        return len(self.items)

    def set_new_item(self, value: str):
        """Set the new_item var from the input's on_change event."""
        self.new_item = value

    def add_item(self):
        """Add the current new_item to the items list and clear the input."""
        self.items.append(self.new_item)
        self.new_item = ""

    def remove_item(self, index: int):
        """Remove an item from the items list by its integer index."""
        self.items.pop(index)


def render_item(item: tuple[str, int]) -> rx.Component:
    """Render a single todo item row with text and a Remove button."""
    text, index = item
    return rx.hstack(
        rx.text(text),
        rx.button(
            "Remove",
            on_click=lambda: State.remove_item(index),
        ),
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Todo List", size="9"),
            rx.hstack(
                rx.input(
                    placeholder="Enter a new todo...",
                    value=State.new_item,
                    on_change=State.set_new_item,
                ),
                rx.button("Add", on_click=State.add_item),
            ),
            rx.foreach(State.items, render_item),
            rx.text("Total: ", State.total),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
