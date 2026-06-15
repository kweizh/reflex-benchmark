"""Reflex Counter App with Parity Badge."""

import reflex as rx


class State(rx.State):
    """The app state with a counter and parity computed var."""

    count: int = 0

    def increment(self) -> None:
        """Increment the count by 1."""
        self.count += 1

    def decrement(self) -> None:
        """Decrement the count by 1."""
        self.count -= 1

    def reset_count(self) -> None:
        """Reset the count to 0."""
        self.count = 0

    @rx.var(cache=True)
    def parity(self) -> str:
        """Return 'even' or 'odd' based on the current count."""
        if self.count % 2 == 0:
            return "even"
        else:
            return "odd"


def index() -> rx.Component:
    """The main page layout."""
    return rx.container(
        rx.vstack(
            rx.heading(
                "Count: ",
                State.count,
                size="7",
            ),
            rx.hstack(
                rx.button("Increment", on_click=State.increment),
                rx.button("Decrement", on_click=State.decrement),
                rx.button("Reset", on_click=State.reset_count),
                spacing="4",
            ),
            rx.badge(
                State.parity,
                color_scheme=rx.cond(State.parity == "even", "green", "red"),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)