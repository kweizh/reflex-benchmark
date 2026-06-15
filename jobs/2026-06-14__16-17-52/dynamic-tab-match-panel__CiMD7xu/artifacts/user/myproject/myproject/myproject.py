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
        rx.vstack(
            # Tab buttons
            rx.hstack(
                rx.button(
                    "Profile",
                    on_click=State.set_active_tab("profile"),
                ),
                rx.button(
                    "Settings",
                    on_click=State.set_active_tab("settings"),
                ),
                rx.button(
                    "About",
                    on_click=State.set_active_tab("about"),
                ),
                spacing="3",
            ),
            # Match-based panel
            rx.match(
                State.active_tab,
                ("profile", rx.text("User Profile Page")),
                ("settings", rx.text("Settings Page")),
                ("about", rx.text("About Page")),
                rx.text("Unknown Tab"),
            ),
            spacing="5",
            padding="4",
        ),
    )


app = rx.App()
app.add_page(index)
