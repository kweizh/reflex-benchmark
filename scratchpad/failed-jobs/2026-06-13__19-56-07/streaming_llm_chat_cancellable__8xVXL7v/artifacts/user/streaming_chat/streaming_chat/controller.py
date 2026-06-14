import asyncio
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

class SendRequest(BaseModel):
    prompt: str

class StatusResponse(BaseModel):
    is_streaming: bool
    current_response: str
    chunks_streamed: number
    was_cancelled: bool
    completed: bool

class StreamingController:
    def __init__(self):
        self.is_streaming = False
        self.current_response = ""
        self.chunks_streamed = 0
        self.was_cancelled = False
        self.completed = False
        self._should_cancel = False
        self._lock = asyncio.Lock()
        self._current_task: Optional[asyncio.Task] = None

    async def start_streaming(self, prompt: str, state_callback=None):
        async with self._lock:
            if self._current_task and not self._current_task.done():
                self._should_cancel = True
                # Wait a bit for previous task to observe cancellation
                await asyncio.sleep(0.1)
            
            self.is_streaming = True
            self.current_response = ""
            self.chunks_streamed = 0
            self.was_cancelled = False
            self.completed = False
            self._should_cancel = False
            
            self._current_task = asyncio.current_task()

        try:
            tokens = f"Response to: {prompt}. ".split() + [f"token_{i}" for i in range(12)]
            for i, token in enumerate(tokens):
                if self._should_cancel:
                    self.was_cancelled = True
                    break
                
                await asyncio.sleep(0.1) # Simulate work
                
                async with self._lock:
                    self.current_response += token + " "
                    self.chunks_streamed += 1
                
                if state_callback:
                    await state_callback(self.current_response, self.chunks_streamed)
            
            if not self.was_cancelled:
                self.completed = True
        finally:
            async with self._lock:
                self.is_streaming = False

    def cancel(self):
        self._should_cancel = True

controller = StreamingController()
router = APIRouter(prefix="/api/chat")

@router.post("/send")
async def send(req: SendRequest):
    # We trigger the background task. 
    # In Reflex, we usually want the background task to be managed by Reflex if it needs to update State.
    # But for the API, we can run it in the background of the FastAPI loop.
    asyncio.create_task(controller.start_streaming(req.prompt))
    return {"accepted": True}

@router.post("/cancel")
async def cancel():
    controller.cancel()
    return {"cancelled": True}

@router.get("/status")
async def status():
    return {
        "is_streaming": controller.is_streaming,
        "current_response": controller.current_response,
        "chunks_streamed": controller.chunks_streamed,
        "was_cancelled": controller.was_cancelled,
        "completed": controller.completed,
    }
