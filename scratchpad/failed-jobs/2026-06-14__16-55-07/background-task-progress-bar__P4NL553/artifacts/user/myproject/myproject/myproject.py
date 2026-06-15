"""Reflex background task progress bar demo."""

import asyncio

import reflex as rx


class State(rx.State):
    """The app state."""

    progress: int = 0
    status_message: str = "Ready"
    _is_running: bool = False

    @rx.var
    def is_running(self) -> bool:
        return self._is_running

    @rx.event(background=True)
    async def run_task(self):
        # Acquire the lock to mark the task as running and reset state
        async with self:
            self._is_running = True
            self.status_message = "Processing..."
            self.progress = 0

        # Loop five times, sleeping outside the lock for responsiveness
        for i in range(1, 6):
            await asyncio.sleep(0.5)
            async with self:
                self.progress = i * 20

        # Final update: mark completed
        async with self:
            self.status_message = "Completed!"
            self._is_running = False


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Progress Bar Demo", size="7"),
            rx.text(State.status_message),
            rx.progress(value=State.progress),
            rx.button(
                "Start",
                on_click=State.run_task,
                is_disabled=State.is_running,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)