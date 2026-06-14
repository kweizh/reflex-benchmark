import reflex as rx
import asyncio
from fastapi import APIRouter

# --- Module-level Controller ---
class StreamingController:
    def __init__(self):
        self.is_streaming = False
        self.current_response = ""
        self.chunks_streamed = 0
        self.was_cancelled = False
        self.completed = False
        self._should_cancel = False
        self.task = None

controller = StreamingController()

async def stream_generator():
    controller.is_streaming = True
    controller.current_response = ""
    controller.chunks_streamed = 0
    controller.was_cancelled = False
    controller.completed = False
    controller._should_cancel = False

    try:
        for i in range(15):
            if controller._should_cancel:
                controller.was_cancelled = True
                break
                
            await asyncio.sleep(0.1)
            
            controller.current_response += f"token_{i} "
            controller.chunks_streamed += 1
            
            yield controller.current_response
            
        if not controller.was_cancelled:
            controller.completed = True
    finally:
        controller.is_streaming = False

# --- Reflex State ---
class StreamingChatState(rx.State):
    prompt: str = ""
    response: str = ""
    _is_streaming: bool = False
    _should_cancel: bool = False

    def set_prompt(self, prompt: str):
        self.prompt = prompt

    @rx.var
    def is_loading(self) -> bool:
        return self._is_streaming

    @rx.event(background=True)
    async def handle_send(self):
        if controller.task and not controller.task.done():
            controller._should_cancel = True
            await controller.task
            
        async with self:
            self._is_streaming = True
            self._should_cancel = False
            self.response = ""
            
        async def ui_task():
            async for chunk in stream_generator():
                async with self:
                    if self._should_cancel:
                        controller._should_cancel = True
                    self.response = chunk
            
            async with self:
                self._is_streaming = False

        controller.task = asyncio.create_task(ui_task())
        await controller.task

    def handle_cancel(self):
        self._should_cancel = True
        controller._should_cancel = True

# --- UI ---
def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Streaming Chat"),
            rx.hstack(
                rx.input(
                    placeholder="Enter prompt...",
                    on_change=StreamingChatState.set_prompt,
                    value=StreamingChatState.prompt,
                ),
                rx.button("Send", on_click=StreamingChatState.handle_send),
                rx.button("Stop", on_click=StreamingChatState.handle_cancel),
            ),
            rx.cond(
                StreamingChatState.is_loading,
                rx.spinner(),
            ),
            rx.text(StreamingChatState.response),
        )
    )

# --- FastAPI Router ---
router = APIRouter()

@router.post("/api/chat/send")
async def api_send(payload: dict):
    if controller.task and not controller.task.done():
        controller._should_cancel = True
        await controller.task
        
    async def api_task():
        async for _ in stream_generator():
            pass
            
    controller.task = asyncio.create_task(api_task())
    return {"accepted": True}

@router.post("/api/chat/cancel")
async def api_cancel():
    controller._should_cancel = True
    return {"cancelled": True}

@router.get("/api/chat/status")
async def api_status():
    return {
        "is_streaming": controller.is_streaming,
        "current_response": controller.current_response,
        "chunks_streamed": controller.chunks_streamed,
        "was_cancelled": controller.was_cancelled,
        "completed": controller.completed
    }

def api_transformer(app):
    app.include_router(router)

app = rx.App(api_transformer=api_transformer)
app.add_page(index)
