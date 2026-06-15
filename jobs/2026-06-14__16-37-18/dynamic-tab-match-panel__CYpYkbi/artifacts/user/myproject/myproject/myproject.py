import reflex as rx

from rxconfig import config

class State(rx.State):
    active_tab: str = "profile"

    def set_tab(self, tab: str):
        self.active_tab = tab

def index() -> rx.Component:
    return rx.container(
        rx.hstack(
            rx.button("Profile", on_click=lambda: State.set_tab("profile")),
            rx.button("Settings", on_click=lambda: State.set_tab("settings")),
            rx.button("About", on_click=lambda: State.set_tab("about")),
        ),
        rx.match(
            State.active_tab,
            ("profile", rx.text("User Profile Page")),
            ("settings", rx.text("Settings Page")),
            ("about", rx.text("About Page")),
            rx.text("Unknown Tab"),
        )
    )

app = rx.App()
app.add_page(index)
