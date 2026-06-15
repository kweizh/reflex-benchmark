"""Streaming LLM Chat Panel - Simulates token-by-token LLM response streaming."""

import asyncio

import reflex as rx

from rxconfig import config

RESPONSE_CHUNKS = ["Hello", " world", ", this", " is", " streamed", "."]


class State(rx.State):
    """The app state."""

    prompt: str = ""
    response: str = ""
    is_loading: bool = False

    @rx.event
    def set_prompt(self, value: str):
        """Update the prompt state variable."""
        self.prompt = value

    @rx.event
    async def send_prompt(self):
        """Generator event handler that streams a pre-canned response token-by-token."""
        # Clear previous response and mark as loading; yield so spinner appears immediately
        self.response = ""
        self.is_loading = True
        yield

        # Stream each chunk with a small delay so each yield reaches the client
        for chunk in RESPONSE_CHUNKS:
            await asyncio.sleep(0.2)
            self.response += chunk
            yield

        # Done streaming – clear the loading flag
        self.is_loading = False
        yield


def index() -> rx.Component:
    """The main chat panel page."""
    return rx.container(
        rx.vstack(
            rx.heading("Streaming LLM Chat Panel", size="7"),
            rx.text_area(
                placeholder="Type your prompt here…",
                value=State.prompt,
                on_change=State.set_prompt,
                width="100%",
                rows="4",
            ),
            rx.button(
                "Send",
                on_click=State.send_prompt,
                color_scheme="blue",
                width="100%",
            ),
            rx.cond(
                State.is_loading,
                rx.spinner(size="3"),
                rx.fragment(),
            ),
            rx.box(
                rx.text(State.response),
                width="100%",
                min_height="4em",
                padding="1em",
                border="1px solid #ccc",
                border_radius="0.5em",
            ),
            spacing="4",
            width="100%",
            max_width="640px",
            margin="0 auto",
            padding_top="4em",
        ),
    )


app = rx.App()
app.add_page(index)
