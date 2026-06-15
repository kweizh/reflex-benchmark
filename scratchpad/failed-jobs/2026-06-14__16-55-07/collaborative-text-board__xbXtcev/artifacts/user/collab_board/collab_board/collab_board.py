"""Collaborative text board – shared feed backed by a module-level list."""

import asyncio
from datetime import datetime, timezone

import reflex as rx

# ── Module-level shared state ──────────────────────────────────────────────
# This list is the single source of truth for all client sessions.
_GLOBAL_FEED: list[dict] = []


# ── Reflex state ────────────────────────────────────────────────────────────
class State(rx.State):
    """Per-client state that syncs with the browser."""

    feed: list[dict] = []
    username: str = ""
    draft: str = ""
    _stopped: bool = False

    def set_username(self, value: str):
        self.username = value

    def set_draft(self, value: str):
        self.draft = value

    # ── background polling task ──────────────────────────────────────────
    @rx.event(background=True)
    async def poll(self):
        """Continuously sync the module-level feed into per-client state."""
        while not self._stopped:
            await asyncio.sleep(0.5)
            async with self:
                self.feed = list(_GLOBAL_FEED)

    # ── send a message ──────────────────────────────────────────────────
    @rx.event
    def send_message(self):
        """Append a message to the shared feed and clear the draft."""
        _GLOBAL_FEED.append(
            {
                "user": self.username or "anon",
                "text": self.draft,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.draft = ""


# ── Helper for rx.foreach ──────────────────────────────────────────────────
def render_message(msg: dict) -> rx.Component:
    """Render a single message dict as a row in the feed."""
    return rx.hstack(
        rx.text(msg["user"], font_weight="bold"),
        rx.text(": "),
        rx.text(msg["text"]),
        rx.spacer(),
        rx.text(msg["ts"], font_size="0.7em", color="gray"),
        width="100%",
    )


# ── Page ────────────────────────────────────────────────────────────────────
@rx.page(on_load=State.poll)
def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Collaborative Board", size="5"),
            # Username input
            rx.hstack(
                rx.text("Username:"),
                rx.input(
                    value=State.username,
                    on_change=State.set_username,
                    placeholder="Your name",
                ),
            ),
            # Message input + send button
            rx.hstack(
                rx.input(
                    value=State.draft,
                    on_change=State.set_draft,
                    placeholder="Type a message…",
                    width="60%",
                ),
                rx.button("Send", on_click=State.send_message),
            ),
            rx.divider(),
            # Feed
            rx.foreach(State.feed, render_message),
            spacing="4",
            align="stretch",
        ),
    )


app = rx.App()