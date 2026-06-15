"""Collaborative Text Board - Shared message feed using Reflex background tasks."""

import asyncio
import time

import reflex as rx

from rxconfig import config

# ---------------------------------------------------------------------------
# Module-level shared state — single source of truth across ALL sessions.
# This list is intentionally NOT a State attribute so that mutations made in
# one client's event handler are visible to every other connected client.
# ---------------------------------------------------------------------------
_GLOBAL_FEED: list[dict] = []


class State(rx.State):
    """Per-client state for the collaborative board."""

    # Public (serialised to the browser) vars
    feed: list[dict] = []
    username: str = ""
    draft: str = ""

    # Backend-only var — leading underscore keeps it out of the serialised
    # state delta that is sent to the frontend.
    _stopped: bool = False

    # ------------------------------------------------------------------
    # Background polling handler
    # ------------------------------------------------------------------

    @rx.event(background=True)
    async def poll(self):
        """Long-running loop that pushes _GLOBAL_FEED into self.feed.

        The asyncio.sleep **must** live outside the async with self: block so
        that the state lock is not held during the sleep — other handlers
        (e.g. send_message) need to acquire the lock too.
        """
        while True:
            # Release the lock while waiting — other handlers can run freely.
            await asyncio.sleep(0.5)

            async with self:
                # Check the stop flag under the lock.
                if self._stopped:
                    break
                # Copy a snapshot of the shared list into the client's state.
                self.feed = list(_GLOBAL_FEED)

    # ------------------------------------------------------------------
    # Standard (synchronous) event handlers
    # ------------------------------------------------------------------

    def send_message(self):
        """Append a message to the global feed and clear the draft input."""
        text = self.draft.strip()
        if not text:
            return

        entry = {
            "user": self.username.strip() or "anon",
            "text": text,
            "ts": time.time(),
        }

        # Mutate the module-level list — NOT self.feed.
        _GLOBAL_FEED.append(entry)

        # Clear the draft so the input box empties immediately.
        self.draft = ""

        # Give the sender an instant local update without waiting for the
        # next poll cycle.
        self.feed = list(_GLOBAL_FEED)

    def set_username(self, value: str):
        self.username = value

    def set_draft(self, value: str):
        self.draft = value

    def stop_polling(self):
        """Set the flag that tells the background task to exit its loop."""
        self._stopped = True


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def message_item(entry: dict) -> rx.Component:
    """Render a single feed entry."""
    return rx.box(
        rx.hstack(
            rx.badge(
                rx.text(entry["user"], weight="bold"),
                color_scheme="blue",
                variant="soft",
            ),
            rx.text(entry["text"], flex="1"),
            spacing="2",
            align="start",
            width="100%",
        ),
        padding="0.5em",
        border_radius="6px",
        border="1px solid var(--gray-4)",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


@rx.page(route="/", on_load=State.poll)
def index() -> rx.Component:
    """Main page for the collaborative text board."""
    return rx.container(
        rx.vstack(
            # --- Header ---
            rx.heading("📋 Collaborative Text Board", size="7", margin_bottom="0.5em"),
            rx.text(
                "Messages are shared in real-time across all connected clients.",
                color_scheme="gray",
                size="2",
            ),
            rx.divider(margin_y="1em"),

            # --- Username input ---
            rx.hstack(
                rx.text("Username:", min_width="80px", weight="bold"),
                rx.input(
                    placeholder="Enter your name (optional)",
                    value=State.username,
                    on_change=State.set_username,
                    width="300px",
                    id="username-input",
                ),
                align="center",
                spacing="3",
                width="100%",
            ),

            # --- Message compose area ---
            rx.hstack(
                rx.input(
                    placeholder="Type a message…",
                    value=State.draft,
                    on_change=State.set_draft,
                    on_key_down=rx.cond(
                        rx.Var.create("event.key") == "Enter",
                        State.send_message,
                        rx.console_log(""),
                    ),
                    flex="1",
                    id="draft-input",
                ),
                rx.button(
                    "Send",
                    on_click=State.send_message,
                    color_scheme="blue",
                    id="send-button",
                ),
                spacing="2",
                width="100%",
            ),

            rx.divider(margin_y="1em"),

            # --- Feed ---
            rx.text("Messages:", weight="bold", size="3"),
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(State.feed, message_item),
                    spacing="2",
                    width="100%",
                ),
                height="400px",
                width="100%",
                type="always",
            ),

            spacing="3",
            width="100%",
            max_width="700px",
            padding="2em",
            align="start",
        ),
        padding="2em",
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = rx.App()
