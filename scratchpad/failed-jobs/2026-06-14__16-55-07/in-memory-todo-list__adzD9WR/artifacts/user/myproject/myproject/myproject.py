"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    new_item: str = ""
    items: list[str] = []

    @rx.var(cache=True)
    def total(self) -> int:
        return len(self.items)

    def add_item(self):
        if self.new_item:
            self.items.append(self.new_item)
            self.new_item = ""

    def remove_item(self, index: int):
        self.items.pop(index)

    def set_new_item(self, value: str):
        self.new_item = value


def render_item(item: str, index: int) -> rx.Component:
    return rx.hstack(
        rx.text(item),
        rx.button("Remove", on_click=lambda: State.remove_item(index)),
        spacing="3",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Todo List", size="6"),
            rx.hstack(
                rx.input(
                    value=State.new_item,
                    on_change=State.set_new_item,
                    placeholder="New item...",
                ),
                rx.button("Add", on_click=State.add_item),
                spacing="3",
            ),
            rx.foreach(State.items, render_item),
            rx.text("Total: ", State.total),
            spacing="3",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)