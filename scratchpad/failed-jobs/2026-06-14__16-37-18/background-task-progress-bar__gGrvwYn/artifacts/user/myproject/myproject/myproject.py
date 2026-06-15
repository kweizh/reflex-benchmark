"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import asyncio
import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""
    progress: int = 0
    status_message: str = "Ready"
    _running: bool = False

    @rx.event(background=True)
    async def start_task(self):
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
    # Welcome Page (Index)
    return rx.container(
        rx.vstack(
            rx.heading("Background Task Progress", size="9"),
            rx.text(State.status_message, size="5"),
            rx.progress(value=State.progress),
            rx.button(
                "Start",
                on_click=State.start_task,
                disabled=State._running,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
