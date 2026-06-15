"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    theme: str = rx.Cookie("light", name="app_theme")

    def toggle_theme(self):
        if self.theme == "light":
            self.theme = "dark"
        else:
            self.theme = "light"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading(f"Current: {State.theme}"),
            rx.button("Toggle Theme", on_click=State.toggle_theme),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)