"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import asyncio
import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""
    prompt: str = ""
    response: str = ""
    is_loading: bool = False

    @rx.event
    def set_prompt(self, val: str):
        """Set the prompt value."""
        self.prompt = val

    @rx.event
    async def start_streaming(self):
        """Simulate streaming response."""
        self.response = ""
        self.is_loading = True
        yield

        chunks = ["Hello", " world", ", this", " is", " streamed", "."]
        for chunk in chunks:
            self.response += chunk
            yield
            await asyncio.sleep(0.2)

        self.is_loading = False
        yield


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.vstack(
            rx.heading("Simulated LLM Streaming Chat Panel", size="7"),
            rx.text_area(
                value=State.prompt,
                on_change=State.set_prompt,
                placeholder="Type your prompt here...",
                width="100%",
            ),
            rx.button(
                "Send",
                on_click=State.start_streaming,
            ),
            rx.box(
                rx.text(State.response),
                padding="1em",
                border="1px solid #ccc",
                border_radius="4px",
                width="100%",
                min_height="100px",
            ),
            rx.cond(
                State.is_loading,
                rx.spinner(),
                rx.fragment(),
            ),
            spacing="4",
            align_items="center",
            width="100%",
        ),
        padding="2em",
    )


app = rx.App()
app.add_page(index)
