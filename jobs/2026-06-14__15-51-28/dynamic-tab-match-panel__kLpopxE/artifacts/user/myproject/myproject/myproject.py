"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""
    active_tab: str = "profile"

    def set_active_tab(self, tab: str):
        self.active_tab = tab


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Dynamic Tab-Based Match Panel", size="7"),
            rx.hstack(
                rx.button("Profile", on_click=State.set_active_tab("profile")),
                rx.button("Settings", on_click=State.set_active_tab("settings")),
                rx.button("About", on_click=State.set_active_tab("about")),
                spacing="4",
            ),
            rx.match(
                State.active_tab,
                ("profile", rx.text("User Profile Page")),
                ("settings", rx.text("Settings Page")),
                ("about", rx.text("About Page")),
                rx.text("Unknown Tab"),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
