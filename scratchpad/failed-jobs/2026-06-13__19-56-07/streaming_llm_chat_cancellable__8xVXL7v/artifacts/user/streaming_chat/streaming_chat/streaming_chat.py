import asyncio
import random
from typing import Optional
import reflex as rx
from fastapi import APIRouter
from pydantic import BaseModel

# --- Controller Logic (Shared between API and State) ---

class StreamingController:
    def __init__(self):
        self.is_streaming = False
        self.current_response = ""
        self.chunks_streamed = 0
        self.was_cancelled = False
        self.completed = False
        self._should_cancel = False
        self._lock = asyncio.Lock()

    async def run_streaming(self, prompt: str, update_fn=None):
        async with self._lock:
            # If already streaming, signal cancel and reset
            self._should_cancel = True
        
        # Give a moment for any existing loop to catch the cancel signal
        await asyncio.sleep(0.1)

        async with self._lock:
            self.is_streaming = True
            self.current_response = ""
            self.chunks_streamed = 0
            self.was_cancelled = False
            self.completed = False
            self._should_cancel = False

        try:
            # At least 12 chunks
            base_text = f"Simulated response to '{prompt}': "
            tokens = base_text.split() + [f"chunk_{i+1}" for i in range(12)]
            
            for token in tokens:
                # Cooperative cancellation check
                if self._should_cancel:
                    self.was_cancelled = True
                    break
                
                # Sleep between 50ms and 250ms
                await asyncio.sleep(random.uniform(0.05, 0.25))
                
                async with self._lock:
                    self.current_response += token + " "
                    self.chunks_streamed += 1
                    curr_resp = self.current_response
                    curr_chunks = self.chunks_streamed
                
                if update_fn:
                    await update_fn(curr_resp, curr_chunks)
            
            if not self.was_cancelled:
                self.completed = True
        finally:
            async with self._lock:
                self.is_streaming = False
                if update_fn:
                    await update_fn(None, None, finalize=True)

    def trigger_cancel(self):
        self._should_cancel = True

# Global controller instance
controller = StreamingController()

# --- FastAPI Router ---

router = APIRouter(prefix="/api/chat")

class SendRequest(BaseModel):
    prompt: str

@router.post("/send")
async def api_send(req: SendRequest):
    # Start the background task in the global event loop
    asyncio.create_task(controller.run_streaming(req.prompt))
    return {"accepted": True}

@router.post("/cancel")
async def api_cancel():
    controller.trigger_cancel()
    return {"cancelled": True}

@router.get("/status")
async def api_status():
    return {
        "is_streaming": controller.is_streaming,
        "current_response": controller.current_response,
        "chunks_streamed": controller.chunks_streamed,
        "was_cancelled": controller.was_cancelled,
        "completed": controller.completed,
    }

# --- Reflex State ---

class StreamingChatState(rx.State):
    prompt: str = ""
    response_text: str = ""
    chunks_count: int = 0
    
    # Backend-only flags
    _is_streaming: bool = False
    _should_cancel: bool = False
    _was_cancelled: bool = False
    _completed: bool = False

    @rx.var
    def is_loading(self) -> bool:
        return self._is_streaming

    @rx.event
    def set_prompt(self, val: str):
        self.prompt = val

    @rx.event
    def stop_streaming(self):
        self._should_cancel = True
        controller.trigger_cancel()

    @rx.event(background=True)
    async def handle_send(self):
        async with self:
            if not self.prompt:
                return
            prompt_to_use = self.prompt
            self._is_streaming = True
            self._should_cancel = False
            self.response_text = ""
            self.chunks_count = 0
            self._was_cancelled = False
            self._completed = False
        
        # Use the shared controller
        await controller.run_streaming(prompt_to_use, update_fn=self._update_state)

    async def _update_state(self, text, chunks, finalize=False):
        async with self:
            if finalize:
                self._is_streaming = False
                self._was_cancelled = controller.was_cancelled
                self._completed = controller.completed
            else:
                self.response_text = text
                self.chunks_count = chunks
                # Sync back the cancel flag if it was set via stop_streaming event
                if self._should_cancel:
                    controller.trigger_cancel()

# --- UI ---

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Streaming Chat", size="8"),
            rx.input(
                placeholder="Enter your prompt...",
                on_change=StreamingChatState.set_prompt,
                value=StreamingChatState.prompt,
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    "Send", 
                    on_click=StreamingChatState.handle_send,
                    disabled=StreamingChatState.is_loading
                ),
                rx.button(
                    "Stop", 
                    on_click=StreamingChatState.stop_streaming,
                    color_scheme="red",
                    disabled=~StreamingChatState.is_loading
                ),
            ),
            rx.cond(
                StreamingChatState.is_loading,
                rx.chakra.spinner(color="blue", size="md"),
            ),
            rx.box(
                rx.text(StreamingChatState.response_text),
                padding="1em",
                border="1px solid #ccc",
                border_radius="5px",
                width="100%",
                min_height="100px",
            ),
            rx.text(f"Chunks: {StreamingChatState.chunks_count}"),
            width="50%",
            spacing="4",
            padding="2em",
        ),
        height="100vh",
    )

app = rx.App(api_transformer=lambda app: app.include_router(router))
app.add_page(index)
