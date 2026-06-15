"""Streaming LLM Chat Panel - A Reflex app that simulates streaming LLM responses."""

import asyncio

import reflex as rx


class State(rx.State):
    """The app state for the streaming LLM panel."""

    prompt: str = ""
    response: str = ""
    is_loading: bool = False

    @rx.event
    def set_prompt(self, value: str):
        self.prompt = value

    @rx.event
    async def send(self):
        """Simulate streaming an LLM response token-by-token."""
        self.is_loading = True
        yield

        chunks = ["Hello", " world", ", this", " is", " streamed", "."]
        for chunk in chunks:
            await asyncio.sleep(0.2)
            self.response += chunk
            yield

        self.is_loading = False
        yield


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Streaming LLM Panel", size="8"),
            rx.text_area(
                placeholder="Type your prompt here...",
                value=State.prompt,
                on_change=State.set_prompt,
                width="100%",
                min_height="100px",
            ),
            rx.button(
                "Send",
                on_click=State.send,
                loading=State.is_loading,
            ),
            rx.cond(
                State.is_loading,
                rx.spinner(size="2"),
                rx.fragment(),
            ),
            rx.cond(
                State.response != "",
                rx.box(
                    rx.text(State.response, white_space="pre-wrap"),
                    padding="1em",
                    border="1px solid #e0e0e0",
                    border_radius="8px",
                    width="100%",
                    min_height="50px",
                ),
                rx.fragment(),
            ),
            spacing="4",
            align="start",
            width="100%",
            max_width="600px",
            margin_top="2em",
        ),
        center_content=True,
    )


app = rx.App()
app.add_page(index)
