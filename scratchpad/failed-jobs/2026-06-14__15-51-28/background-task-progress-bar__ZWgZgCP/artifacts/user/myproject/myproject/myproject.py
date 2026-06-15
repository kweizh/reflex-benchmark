import asyncio
import reflex as rx


class State(rx.State):
    progress: int = 0
    status_message: str = "Ready"
    _running: bool = False

    @rx.var
    def is_running(self) -> bool:
        return self._running

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
    return rx.center(
        rx.vstack(
            rx.text(State.status_message),
            rx.progress(value=State.progress, width="100%"),
            rx.button("Start", on_click=State.start_task, disabled=State.is_running),
            spacing="4",
            align="center",
            width="300px",
        ),
        height="100vh",
    )


app = rx.App()
app.add_page(index)
