import reflex as rx
import asyncio
import time

_GLOBAL_FEED: list[dict] = []

class State(rx.State):
    feed: list[dict] = []
    username: str = ""
    draft: str = ""
    _stopped: bool = False

    def set_username(self, val: str):
        self.username = val

    def set_draft(self, val: str):
        self.draft = val

    @rx.event(background=True)
    async def poll(self):
        while True:
            await asyncio.sleep(0.5)
            async with self:
                if self._stopped:
                    break
                self.feed = list(_GLOBAL_FEED)

    def send_message(self):
        msg = {
            "user": self.username or "anon",
            "text": self.draft,
            "ts": time.time()
        }
        _GLOBAL_FEED.append(msg)
        self.draft = ""

def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Collaborative Board"),
        rx.input(
            placeholder="Username",
            value=State.username,
            on_change=State.set_username,
        ),
        rx.input(
            placeholder="Message",
            value=State.draft,
            on_change=State.set_draft,
        ),
        rx.button("Send", on_click=State.send_message),
        rx.vstack(
            rx.foreach(
                State.feed,
                lambda msg: rx.text(msg["user"].to(str) + ": " + msg["text"].to(str))
            )
        )
    )

app = rx.App()
app.add_page(index, on_load=State.poll)
