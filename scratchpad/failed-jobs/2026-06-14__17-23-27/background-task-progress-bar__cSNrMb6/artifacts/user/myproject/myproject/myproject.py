"""Background task progress bar demo."""

import asyncio

import reflex as rx


class State(rx.State):
    """The app state."""

    progress: int = 0
    status_message: str = "Ready"
    _running: bool = False

    @rx.event(background=True)
    async def start_task(self):
        """Simulate a long-running operation with progress updates."""
        async with self:
            self._running = True
            self.status_message = "Processing..."
            self.progress = 0

        for i in range(1, 6):
            await asyncio.sleep(0.5)
            async with self:
                self.progress = i * 20

        async with self:
            self.status_message = "Completed!"
            self._running = False


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Background Task Progress", size="7"),
            rx.button(
                "Start",
                on_click=State.start_task,
                disabled=State._running,
            ),
            rx.text(State.status_message),
            rx.progress(value=State.progress),
            spacing="5",
            justify="center",
            min_height="85vh",
            align="center",
        ),
    )


app = rx.App()
app.add_page(index)
