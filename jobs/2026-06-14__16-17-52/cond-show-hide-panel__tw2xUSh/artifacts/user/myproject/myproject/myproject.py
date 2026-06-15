"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    show_panel: bool = False

    def toggle_panel(self, value: bool):
        self.show_panel = value

    @rx.var(cache=True)
    def visibility_label(self) -> str:
        if self.show_panel:
            return "Visibility: shown"
        return "Visibility: hidden"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Conditional Panel Demo", size="7"),
            rx.hstack(
                rx.text("Toggle Panel:"),
                rx.switch(
                    checked=State.show_panel,
                    on_change=State.toggle_panel,
                ),
                align="center",
                spacing="3",
            ),
            rx.cond(
                State.show_panel,
                rx.box(
                    rx.text("Secret Panel Content"),
                    padding="4",
                    border="1px solid #ccc",
                    border_radius="md",
                    background="lightblue",
                ),
                rx.fragment(),
            ),
            rx.cond(
                State.show_panel,
                rx.text("Visibility: shown"),
                rx.text("Visibility: hidden"),
            ),
            spacing="5",
            padding="8",
        ),
    )


app = rx.App()
app.add_page(index)
