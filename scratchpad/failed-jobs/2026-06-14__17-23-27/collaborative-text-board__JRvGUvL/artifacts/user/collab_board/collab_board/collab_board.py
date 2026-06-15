"""Collaborative text board application using Reflex background tasks."""

import asyncio
import time

import reflex as rx

# Module-level shared feed — the single source of truth across all client sessions.
_GLOBAL_FEED: list[dict] = []


class State(rx.State):
    """The shared collaborative board state."""

    # Per-client view of the feed, synchronized from _GLOBAL_FEED by the poll loop.
    feed: list[dict] = []

    # The username typed in the username input.
    username: str = ""

    # The current value of the message input.
    draft: str = ""

    # Backend-only flag used to stop the polling loop.
    _stopped: bool = False

    @rx.event(background=True)
    async def poll(self) -> None:
        """Background task that polls _GLOBAL_FEED and pushes updates to the client."""
        while True:
            # Sleep outside the state lock to avoid blocking other state mutations.
            await asyncio.sleep(0.5)

            # Enter the state lock to safely mutate state.
            async with self:
                if self._stopped:
                    break
                # Copy a snapshot of the module-level list into the per-client feed.
                self.feed = list(_GLOBAL_FEED)

    def send_message(self) -> None:
        """Append a message to the shared feed and clear the draft."""
        if not self.draft.strip():
            return

        entry = {
            "user": self.username.strip() or "anon",
            "text": self.draft.strip(),
            "ts": time.time(),
        }
        _GLOBAL_FEED.append(entry)
        # Clear the draft so the input resets.
        self.draft = ""
        # Immediately sync the sender's own view.
        self.feed = list(_GLOBAL_FEED)


def index() -> rx.Component:
    """Render the collaborative text board UI."""
    return rx.container(
        rx.vstack(
            rx.heading("Collaborative Text Board", size="8"),
            rx.text("Share messages in real-time with other connected clients."),
            rx.hstack(
                rx.input(
                    placeholder="Your name...",
                    value=State.username,
                    on_change=State.set_username,
                    width="200px",
                ),
                rx.input(
                    placeholder="Type a message...",
                    value=State.draft,
                    on_change=State.set_draft,
                    width="400px",
                    on_key_down=lambda: rx.call_cond(
                        State.draft.strip() != "",
                        State.send_message,
                    ),
                ),
                rx.button("Send", on_click=State.send_message),
                spacing="3",
                align="center",
            ),
            rx.divider(),
            rx.vstack(
                rx.foreach(
                    State.feed,
                    lambda msg: rx.card(
                        rx.hstack(
                            rx.text(msg["user"], weight="bold", color_scheme="blue"),
                            rx.text("—"),
                            rx.text(msg["text"]),
                            spacing="2",
                        ),
                    ),
                ),
                spacing="2",
                align="stretch",
                width="100%",
            ),
            spacing="5",
            align="stretch",
            padding="2em",
        ),
        max_width="700px",
    )


app = rx.App()
app.add_page(index, on_load=State.poll)
