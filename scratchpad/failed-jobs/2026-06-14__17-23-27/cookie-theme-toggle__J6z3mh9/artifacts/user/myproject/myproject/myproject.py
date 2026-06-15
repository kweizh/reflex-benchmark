"""A Reflex app with a cookie-persisted theme toggle."""

import reflex as rx


class State(rx.State):
    """The app state."""

    theme: str = rx.Cookie("light", name="app_theme")

    def toggle_theme(self):
        """Toggle the theme between light and dark."""
        if self.theme == "light":
            self.theme = "dark"
        else:
            self.theme = "light"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading(f"Current: {State.theme}"),
            rx.button(
                "Toggle Theme",
                on_click=State.toggle_theme,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
