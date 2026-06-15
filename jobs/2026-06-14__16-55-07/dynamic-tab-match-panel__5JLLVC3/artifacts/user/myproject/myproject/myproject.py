"""Tab-based match panel using rx.match."""

import reflex as rx


class State(rx.State):
    """The app state."""

    active_tab: str = "profile"

    def set_tab(self, tab: str):
        """Set the active tab to the lowercased label."""
        self.active_tab = tab.lower()


def index() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.button("Profile", on_click=State.set_tab("profile")),
            rx.button("Settings", on_click=State.set_tab("settings")),
            rx.button("About", on_click=State.set_tab("about")),
            spacing="4",
        ),
        rx.match(
            State.active_tab,
            ("profile", rx.text("User Profile Page")),
            ("settings", rx.text("Settings Page")),
            ("about", rx.text("About Page")),
            rx.text("Unknown Tab"),
        ),
        spacing="4",
        padding="2em",
    )


app = rx.App()
app.add_page(index)