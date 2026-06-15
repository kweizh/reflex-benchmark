"""Reflex Counter with Parity Badge application."""

import reflex as rx


class State(rx.State):
    """The app state."""

    count: int = 0

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1

    def reset_count(self):
        self.count = 0

    @rx.var(cache=True)
    def parity(self) -> str:
        if self.count % 2 == 0:
            return "even"
        else:
            return "odd"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading(f"Count: {State.count}"),
            rx.hstack(
                rx.button("Increment", on_click=State.increment),
                rx.button("Decrement", on_click=State.decrement),
                rx.button("Reset", on_click=State.reset_count),
                spacing="2",
            ),
            rx.badge(
                State.parity,
                color_scheme=rx.cond(
                    State.parity == "even",
                    "green",
                    "red",
                ),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
