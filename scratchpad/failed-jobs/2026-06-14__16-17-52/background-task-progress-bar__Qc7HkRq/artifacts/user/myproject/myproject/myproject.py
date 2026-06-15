"""Reflex app with a background task progress bar."""

import asyncio

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    progress: int = 0
    status_message: str = "Ready"
    _is_running: bool = False

    @rx.event(background=True)
    async def run_task(self):
        """Simulate a long-running background task in five steps."""
        # Acquire lock to mark task as running and reset state
        async with self:
            self._is_running = True
            self.status_message = "Processing..."
            self.progress = 0

        # Loop five times, sleeping OUTSIDE the lock for UI responsiveness
        for i in range(1, 6):
            await asyncio.sleep(0.5)
            async with self:
                self.progress = i * 20

        # Acquire lock to finalize state
        async with self:
            self.status_message = "Completed!"
            self._is_running = False


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Background Task Demo", size="7"),
            rx.button(
                "Start",
                on_click=State.run_task,
                disabled=State._is_running,
            ),
            rx.text(State.status_message),
            rx.progress(value=State.progress, max=100, width="100%"),
            spacing="4",
            align="center",
            min_height="50vh",
            justify="center",
        ),
    )


app = rx.App()
app.add_page(index)
