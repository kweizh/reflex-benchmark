"""Reflex app with conditional panel and cached visibility label."""

import reflex as rx


class State(rx.State):
    """The app state."""

    show_panel: bool = False

    def set_show_panel(self, value: bool):
        """Set whether the panel is shown."""
        self.show_panel = value

    @rx.var(cache=True)
    def visibility_label(self) -> str:
        """Return a human-readable label for the panel visibility."""
        return "Visibility: shown" if self.show_panel else "Visibility: hidden"


def index() -> rx.Component:
    """The main page."""
    return rx.container(
        rx.vstack(
            rx.switch(on_change=State.set_show_panel),
            rx.cond(
                State.show_panel,
                rx.text("Visibility: shown"),
                rx.text("Visibility: hidden"),
            ),
            rx.cond(
                State.show_panel,
                rx.box("Secret Panel Content"),
            ),
            spacing="4",
            align="start",
        ),
    )


app = rx.App()
app.add_page(index)