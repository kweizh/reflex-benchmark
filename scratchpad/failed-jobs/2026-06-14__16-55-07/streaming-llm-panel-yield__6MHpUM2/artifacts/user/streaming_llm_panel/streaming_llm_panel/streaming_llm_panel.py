"""Simulated LLM Streaming Chat Panel with Reflex."""

import asyncio

import reflex as rx


class State(rx.State):
    """The app state for the streaming LLM panel."""

    prompt: str = ""
    response: str = ""
    is_loading: bool = False

    def set_prompt(self, value: str):
        """Set the prompt value from the text area."""
        self.prompt = value

    @rx.event
    async def send_message(self) -> None:
        """Async generator event handler that simulates streaming an LLM response."""
        self.is_loading = True
        self.response = ""
        yield

        chunks = ["Hello", " world", ", this", " is", " streamed", "."]
        for chunk in chunks:
            self.response += chunk
            yield
            await asyncio.sleep(0.2)

        self.is_loading = False
        yield


def index() -> rx.Component:
    """The main page component."""
    return rx.container(
        rx.vstack(
            rx.heading("LLM Chat Panel", size="7"),
            rx.text_area(
                placeholder="Type your prompt...",
                value=State.prompt,
                on_change=State.set_prompt,
                width="100%",
            ),
            rx.button(
                "Send",
                on_click=State.send_message,
                width="100%",
            ),
            rx.divider(),
            rx.text(
                State.response,
                size="4",
                width="100%",
            ),
            rx.cond(
                State.is_loading,
                rx.spinner(),
                rx.fragment(),
            ),
            spacing="4",
            align="stretch",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)