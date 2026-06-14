"""Multi-room chat application with streaming assistant replies."""

from __future__ import annotations

import asyncio
import datetime

import reflex as rx
from sqlmodel import select


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------


class Message(rx.Model, table=True):
    """A single chat message persisted in SQLite."""

    room: str
    sender: str
    content: str
    created_at: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_message(room: str, sender: str, content: str) -> Message:
    """Insert a message row into the database and return it."""
    msg = Message(
        room=room,
        sender=sender,
        content=content,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    with rx.session() as sess:
        sess.add(msg)
        sess.commit()
        sess.refresh(msg)
    return msg


def _get_messages_for_room(room: str) -> list[dict]:
    """Return all messages for *room* as plain dicts, oldest first."""
    with rx.session() as sess:
        rows = sess.exec(
            select(Message).where(Message.room == room).order_by(Message.id)
        ).all()
        return [
            {
                "id": m.id,
                "room": m.room,
                "sender": m.sender,
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in rows
        ]


def _get_rooms() -> list[str]:
    """Return the distinct room names from the DB."""
    with rx.session() as sess:
        rows = sess.exec(select(Message.room).distinct()).all()
        return sorted(rows)


# ---------------------------------------------------------------------------
# Canned assistant replies – each split into ≥5 tokens
# ---------------------------------------------------------------------------

ASSISTANT_REPLIES: list[str] = [
    "Hello! How can I help you today?",
    "That's a great question! Let me think about it.",
    "Thanks for sharing! Here's what I think.",
    "Interesting point! I'd love to discuss this further.",
    "Welcome to the chat room! Feel free to ask anything.",
]


def _split_reply(text: str, n: int = 5) -> list[str]:
    """Split *text* into *n* roughly equal non-empty chunks."""
    length = len(text)
    chunk_size = max(length // n, 1)
    parts: list[str] = []
    for i in range(n):
        start = i * chunk_size
        if i == n - 1:
            parts.append(text[start:])
        else:
            parts.append(text[start : start + chunk_size])
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------


class ChatState(rx.State):
    """State for the multi-room chat UI."""

    current_room: str = "general"
    rooms: list[str] = []
    current_messages: list[dict] = []
    new_room_name: str = ""
    message_input: str = ""
    assistant_streaming: str = ""

    # ---- lifecycle ---------------------------------------------------------

    def on_load(self):
        """Seed rooms on first page-load and hydrate state from DB."""
        existing = _get_rooms()
        if not existing:
            # Seed: create and immediately clear system messages
            _create_message("general", "system", "Room created")
            _create_message("random", "system", "Room created")
            with rx.session() as sess:
                for m in sess.exec(select(Message)).all():
                    sess.delete(m)
                sess.commit()
            self.rooms = ["general", "random"]
        else:
            self.rooms = existing

        # Load messages for the current room
        self.current_messages = _get_messages_for_room(self.current_room)

        # Ensure current_room is valid
        if self.current_room not in self.rooms and self.rooms:
            self.current_room = self.rooms[0]
            self.current_messages = _get_messages_for_room(self.current_room)

    # ---- room management ---------------------------------------------------

    def set_current_room(self, room: str):
        self.current_room = room
        self.current_messages = _get_messages_for_room(room)

    def set_new_room_name(self, name: str):
        self.new_room_name = name

    def add_room(self):
        name = self.new_room_name.strip()
        if not name:
            return
        if name in self.rooms:
            return
        self.rooms = self.rooms + [name]
        self.new_room_name = ""
        # Persist a placeholder so the room exists in DB
        _create_message(name, "system", "Room created")
        # Remove it from displayed messages
        with rx.session() as sess:
            for m in sess.exec(
                select(Message).where(
                    Message.room == name, Message.sender == "system"
                )
            ).all():
                sess.delete(m)
            sess.commit()

    # ---- messaging ---------------------------------------------------------

    def set_message_input(self, value: str):
        self.message_input = value

    async def send_message(self):
        """Send user message and stream assistant reply token-by-token."""
        text = self.message_input.strip()
        if not text:
            return

        room = self.current_room
        self.message_input = ""

        # 1. Persist user message immediately
        user_msg = _create_message(room, "user", text)
        updated_msgs = list(self.current_messages) + [
            {
                "id": user_msg.id,
                "room": user_msg.room,
                "sender": user_msg.sender,
                "content": user_msg.content,
                "created_at": user_msg.created_at,
            }
        ]

        # 2. Stream assistant reply token-by-token
        reply_text = ASSISTANT_REPLIES[hash(text) % len(ASSISTANT_REPLIES)]
        chunks = _split_reply(reply_text, n=5)
        self.assistant_streaming = ""

        for chunk in chunks:
            self.assistant_streaming += chunk
            self.current_messages = list(updated_msgs)
            yield
            await asyncio.sleep(0.05)

        # 3. Persist final assistant message
        asst_msg = _create_message(room, "assistant", reply_text)
        updated_msgs = updated_msgs + [
            {
                "id": asst_msg.id,
                "room": asst_msg.room,
                "sender": asst_msg.sender,
                "content": asst_msg.content,
                "created_at": asst_msg.created_at,
            }
        ]
        self.current_messages = updated_msgs
        self.assistant_streaming = ""
        yield


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _message_bubble(msg: dict) -> rx.Component:
    return rx.box(
        rx.text(
            msg["sender"],
            ": ",
            msg["content"],
        ),
        style={"margin_bottom": "8px"},
    )


# ---------------------------------------------------------------------------
# Page component
# ---------------------------------------------------------------------------


def index() -> rx.Component:
    return rx.container(
        rx.hstack(
            # ---- sidebar ----
            rx.vstack(
                rx.heading("Rooms", size="4"),
                rx.box(
                    rx.foreach(
                        ChatState.rooms,
                        lambda room: rx.button(
                            room,
                            on_click=lambda: ChatState.set_current_room(room),
                            variant=rx.cond(
                                ChatState.current_room == room,
                                "solid",
                                "outline",
                            ),
                            style={"width": "100%", "margin_bottom": "4px"},
                        ),
                    ),
                    id="room-list",
                ),
                rx.hstack(
                    rx.input(
                        placeholder="New room name",
                        value=ChatState.new_room_name,
                        on_change=ChatState.set_new_room_name,
                        id="add-room-input",
                    ),
                    rx.button(
                        "Add",
                        on_click=ChatState.add_room,
                        id="add-room-button",
                    ),
                ),
                width="200px",
                min_height="80vh",
                padding="16px",
                border_right="1px solid #ccc",
            ),
            # ---- main chat area ----
            rx.vstack(
                rx.heading(
                    ChatState.current_room,
                    id="current-room-title",
                ),
                rx.box(
                    rx.cond(
                        ChatState.current_messages.length() == 0,
                        rx.text(
                            "No messages yet — say hi!",
                            id="empty-room-placeholder",
                        ),
                        rx.vstack(
                            rx.foreach(
                                ChatState.current_messages,
                                lambda msg: _message_bubble(msg),
                            ),
                            rx.cond(
                                ChatState.assistant_streaming != "",
                                rx.text(
                                    "assistant: ",
                                    ChatState.assistant_streaming,
                                    font_style="italic",
                                    color="gray",
                                ),
                                rx.fragment(),
                            ),
                        ),
                    ),
                    id="message-list",
                    style={
                        "flex": "1",
                        "overflow_y": "auto",
                        "height": "60vh",
                        "border": "1px solid #ddd",
                        "padding": "8px",
                    },
                ),
                rx.hstack(
                    rx.input(
                        placeholder="Type a message…",
                        value=ChatState.message_input,
                        on_change=ChatState.set_message_input,
                        id="message-input",
                        style={"flex": "1"},
                    ),
                    rx.button(
                        "Send",
                        on_click=ChatState.send_message,
                        id="send-button",
                    ),
                    width="100%",
                ),
                width="100%",
                padding="16px",
            ),
            width="100%",
        ),
        max_width="900px",
    )


# ---------------------------------------------------------------------------
# REST API (FastAPI mounted via api_transformer)
# ---------------------------------------------------------------------------

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

api_app = FastAPI()


@api_app.get("/api/rooms")
async def api_get_rooms():
    rooms = _get_rooms()
    return {"rooms": rooms}


@api_app.post("/api/rooms")
async def api_create_room(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Room name cannot be empty"}, status_code=400)
    existing = _get_rooms()
    if name in existing:
        return JSONResponse({"error": "Room already exists"}, status_code=409)
    _create_message(name, "system", "Room created")
    # Remove the system message so it doesn't appear in message listings
    with rx.session() as sess:
        for m in sess.exec(
            select(Message).where(Message.room == name, Message.sender == "system")
        ).all():
            sess.delete(m)
        sess.commit()
    return JSONResponse({"name": name}, status_code=201)


@api_app.get("/api/messages")
async def api_get_messages(room: str = ""):
    if not room:
        return JSONResponse({"error": "room parameter required"}, status_code=400)
    existing = _get_rooms()
    if room not in existing:
        return JSONResponse({"error": "Room not found"}, status_code=404)
    messages = _get_messages_for_room(room)
    return {"room": room, "messages": messages}


@api_app.post("/api/messages")
async def api_create_message(request: Request):
    body = await request.json()
    room = body.get("room", "")
    content = body.get("content", "")
    if not room:
        return JSONResponse({"error": "room is required"}, status_code=400)
    existing = _get_rooms()
    if room not in existing:
        return JSONResponse({"error": "Room not found"}, status_code=404)
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    # Create user message
    user_msg = _create_message(room, "user", content)

    # Generate assistant reply
    reply_text = ASSISTANT_REPLIES[hash(content) % len(ASSISTANT_REPLIES)]
    chunks = _split_reply(reply_text, n=5)

    # Create assistant message
    asst_msg = _create_message(room, "assistant", reply_text)

    return {
        "user_message": {
            "id": user_msg.id,
            "room": user_msg.room,
            "sender": user_msg.sender,
            "content": user_msg.content,
            "created_at": user_msg.created_at,
        },
        "assistant_chunks": chunks,
        "assistant_message": {
            "id": asst_msg.id,
            "room": asst_msg.room,
            "sender": asst_msg.sender,
            "content": asst_msg.content,
            "created_at": asst_msg.created_at,
        },
    }


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = rx.App(api_transformer=api_app)
app.add_page(index, on_load=ChatState.on_load)