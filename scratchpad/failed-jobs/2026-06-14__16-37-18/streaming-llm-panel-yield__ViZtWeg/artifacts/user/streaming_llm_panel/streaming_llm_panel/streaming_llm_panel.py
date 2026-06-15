import asyncio
import reflex as rx

from rxconfig import config

class State(rx.State):
    """The app state."""
    prompt: str = ""
    response: str = ""
    is_loading: bool = False

    def set_prompt(self, prompt: str):
        self.prompt = prompt

    @rx.event
    async def send_prompt(self):
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
    return rx.container(
        rx.vstack(
            rx.heading("Simulated LLM Chat", size="7"),
            rx.text_area(
                placeholder="Enter your prompt here...",
                value=State.prompt,
                on_change=State.set_prompt,
                width="100%",
            ),
            rx.button(
                "Send",
                on_click=State.send_prompt,
                width="100%",
            ),
            rx.box(
                rx.text(State.response),
                rx.cond(
                    State.is_loading,
                    rx.spinner(),
                    rx.fragment()
                ),
                width="100%",
                min_height="100px",
                border="1px solid #ccc",
                padding="4",
                border_radius="md",
            ),
            spacing="5",
            width="100%",
            max_width="600px",
            margin="0 auto",
            padding_top="10vh",
        )
    )

app = rx.App()
app.add_page(index)
