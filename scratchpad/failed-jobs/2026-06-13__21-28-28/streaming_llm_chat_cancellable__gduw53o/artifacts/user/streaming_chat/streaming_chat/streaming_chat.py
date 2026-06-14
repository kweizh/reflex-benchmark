"""Cancellable streaming LLM chat panel built with Reflex."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import reflex as rx
from fastapi import APIRouter
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Module-level streaming controller
# ---------------------------------------------------------------------------
# Both the Reflex background event and the FastAPI endpoints delegate to this
# object so that the HTTP API exercises the same cancellation / lock semantics
# that the UI does.  Reflex State is per-session and unreachable from plain HTTP,
# hence the indirection through a shared controller.


class StreamingController:
    """Shared mutable controller for the streaming task."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.is_streaming: bool = False
        self.should_cancel: bool = False
        self.current_response: str = ""
        self.chunks_streamed: int = 0
        self.was_cancelled: bool = False
        self.completed: bool = False

    # -- helpers called from both FastAPI and Reflex --------------------------

    def start(self) -> None:
        """Reset state and mark streaming as active."""
        with self._lock:
            # If a previous stream is still running, signal cancellation first.
            if self.is_streaming:
                self.should_cancel = True
            self.is_streaming = True
            self.should_cancel = False
            self.current_response = ""
            self.chunks_streamed = 0
            self.was_cancelled = False
            self.completed = False

    def cancel(self) -> None:
        with self._lock:
            self.should_cancel = True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "is_streaming": self.is_streaming,
                "current_response": self.current_response,
                "chunks_streamed": self.chunks_streamed,
                "was_cancelled": self.was_cancelled,
                "completed": self.completed,
            }

    def mark_chunk(self, text: str) -> None:
        with self._lock:
            self.current_response += text
            self.chunks_streamed += 1

    def finish(self, cancelled: bool) -> None:
        with self._lock:
            self.is_streaming = False
            self.was_cancelled = cancelled
            self.completed = not cancelled


controller = StreamingController()

# Simulated LLM response chunks – at least 12 tokens for an uninterrupted run.
SIMULATED_CHUNKS = [
    "Hello! ",
    "I'm ",
    "a ",
    "simulated ",
    "AI ",
    "assistant. ",
    "Here ",
    "are ",
    "some ",
    "interesting ",
    "facts ",
    "about ",
    "streaming ",
    "technology. ",
    "Thanks ",
    "for asking!",
]


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------


class StreamingChatState(rx.State):
    """Reflex state for the streaming chat UI."""

    # -- publicly visible vars -----------------------------------------------
    prompt: str = ""
    current_response: str = ""
    is_loading: bool = False  # driven by _is_streaming

    # -- backend-only flags (not serialised to the client) ------------------
    _is_streaming: bool = False
    _should_cancel: bool = False

    # -- event handlers -------------------------------------------------------

    @rx.event(background=True)
    async def start_stream(self) -> None:
        """Background event that simulates token-by-token streaming."""
        # Delegate to the shared controller for reset / bookkeeping.
        controller.start()

        # Sync controller state into Reflex state inside the lock.
        async with self:
            self.current_response = ""
            self._is_streaming = True
            self._should_cancel = False
            self.is_loading = True

        for chunk in SIMULATED_CHUNKS:
            # Check the controller cancel flag (cooperative cancellation).
            if controller.should_cancel:
                break

            # Publish this chunk.
            controller.mark_chunk(chunk)

            async with self:
                self.current_response = controller.current_response

            # Sleep between 50 ms and 250 ms.
            await asyncio.sleep(0.1)

            # Re-check after sleep.
            if controller.should_cancel:
                break

        # Determine final status.
        cancelled = controller.should_cancel
        controller.finish(cancelled=cancelled)

        # Reset the streaming flag deterministically.
        async with self:
            self._is_streaming = False
            self._should_cancel = False
            self.is_loading = False
            self.current_response = controller.current_response

    def cancel_stream(self) -> None:
        """Regular event handler – flips the cancel flag."""
        self._should_cancel = True
        controller.cancel()


# ---------------------------------------------------------------------------
# Chat UI page
# ---------------------------------------------------------------------------


def index() -> rx.Component:
    """Main chat page."""
    return rx.container(
        rx.vstack(
            rx.heading("Streaming Chat", size="7"),
            # Prompt input
            rx.hstack(
                rx.input(
                    placeholder="Type a message…",
                    value=StreamingChatState.prompt,
                    on_change=StreamingChatState.set_prompt,
                    width="100%",
                ),
                rx.button(
                    "Send",
                    on_click=StreamingChatState.start_stream(),
                    is_disabled=StreamingChatState.is_loading,
                ),
                rx.button(
                    "Stop",
                    on_click=StreamingChatState.cancel_stream,
                    color_scheme="red",
                    is_disabled=~StreamingChatState.is_loading,
                ),
                width="100%",
            ),
            # Loading indicator
            rx.cond(
                StreamingChatState.is_loading,
                rx.spinner(size="3"),
                rx.fragment(),
            ),
            # Assistant response
            rx.text(
                StreamingChatState.current_response,
                white_space="pre-wrap",
            ),
            spacing="4",
            min_height="85vh",
        ),
    )


# ---------------------------------------------------------------------------
# FastAPI router for external HTTP access
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/chat")


class SendRequest(BaseModel):
    prompt: str


class CancelRequest(BaseModel):
    pass


@router.post("/send")
async def api_send(body: SendRequest) -> dict[str, bool]:
    """Start (or restart) a cancellable streaming background task."""
    controller.start()

    # We also need to kick off the Reflex background event so that the
    # per-chunk ``async with self`` updates reach the UI layer.  The
    # simplest way is to dispatch the event programmatically.
    # However, the FastAPI handler and the Reflex event system are
    # separate.  We rely on the controller for the HTTP contract and
    # use a lightweight asyncio task for the actual streaming work that
    # mirrors the same logic as the Reflex handler.

    # Start an asyncio task that streams chunks.
    asyncio.ensure_future(_run_stream())

    return {"accepted": True}


@router.post("/cancel")
async def api_cancel() -> dict[str, bool]:
    """Set the cooperative cancel flag."""
    controller.cancel()
    return {"cancelled": True}


@router.get("/status")
async def api_status() -> dict[str, Any]:
    """Return the current streaming status."""
    return controller.snapshot()


async def _run_stream() -> None:
    """Pure-async streaming task for the HTTP API path.

    This mirrors the Reflex background handler but operates on the
    module-level controller directly (no Reflex state lock).
    """
    for chunk in SIMULATED_CHUNKS:
        if controller.should_cancel:
            break
        controller.mark_chunk(chunk)
        await asyncio.sleep(0.1)
        if controller.should_cancel:
            break

    cancelled = controller.should_cancel
    controller.finish(cancelled=cancelled)


# ---------------------------------------------------------------------------
# Reflex App with api_transformer
# ---------------------------------------------------------------------------


def _api_transformer(app: rx.App) -> None:
    """Mount the FastAPI router onto the Reflex ASGI app."""
    app.api.include_router(router)


app = rx.App(api_transformer=_api_transformer)
app.add_page(index)