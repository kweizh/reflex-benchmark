import reflex as rx
from datetime import datetime
import asyncio
from typing import List, Dict, Any
from sqlmodel import select, Field
from fastapi import FastAPI, HTTPException

class Room(rx.Model, table=True):
    name: str = Field(unique=True)

class Message(rx.Model, table=True):
    room: str
    sender: str
    content: str
    created_at: datetime = Field(default_factory=datetime.now)

def get_assistant_chunks(content: str) -> List[str]:
    full_reply = f"Assistant reply to: {content}. This is a simulated streaming response with at least five chunks."
    n = 10
    chunk_size = len(full_reply) // n
    chunks = [full_reply[i:i+chunk_size] for i in range(0, (n-1)*chunk_size, chunk_size)]
    chunks.append(full_reply[(n-1)*chunk_size:])
    return chunks

class State(rx.State):
    current_room: str = "general"
    rooms: List[str] = []
    new_room_name: str = ""
    streaming_content: str = ""

    def update_rooms(self):
        with rx.session() as session:
            self.rooms = [r.name for r in session.exec(select(Room)).all()]

    @rx.var
    def active_messages(self) -> List[Message]:
        with rx.session() as session:
            return session.exec(
                select(Message).where(Message.room == self.current_room).order_by(Message.created_at)
            ).all()

    @rx.var
    def messages_by_room(self) -> Dict[str, List[Message]]:
        with rx.session() as session:
            all_messages = session.exec(select(Message).order_by(Message.created_at)).all()
            result = {}
            for msg in all_messages:
                if msg.room not in result:
                    result[msg.room] = []
                result[msg.room].append(msg)
            return result

    def set_new_room_name(self, name: str):
        self.new_room_name = name

    def set_room(self, room: str):
        self.current_room = room
        self.streaming_content = ""

    def add_room(self):
        if self.new_room_name:
            with rx.session() as session:
                if not session.exec(select(Room).where(Room.name == self.new_room_name)).first():
                    session.add(Room(name=self.new_room_name))
                    session.commit()
            self.new_room_name = ""
            self.update_rooms()

    async def send_message(self, form_data: dict):
        content = form_data.get("message_input")
        if not content:
            return
        
        user_msg = Message(room=self.current_room, sender="user", content=content)
        with rx.session() as session:
            session.add(user_msg)
            session.commit()
        
        self.streaming_content = ""
        chunks = get_assistant_chunks(content)
        
        for chunk in chunks:
            self.streaming_content += chunk
            yield
            await asyncio.sleep(0.1)
        
        assistant_msg = Message(room=self.current_room, sender="assistant", content=self.streaming_content)
        with rx.session() as session:
            session.add(assistant_msg)
            session.commit()
        
        self.streaming_content = ""

    def on_load(self):
        with rx.session() as session:
            if not session.exec(select(Room)).first():
                session.add(Room(name="general"))
                session.add(Room(name="random"))
                session.commit()
        self.update_rooms()

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Multi-Room Chat", size="9"),
            rx.hstack(
                rx.vstack(
                    rx.heading("Rooms", size="5"),
                    rx.vstack(
                        rx.foreach(
                            State.rooms,
                            lambda room: rx.button(
                                room,
                                on_click=State.set_room(room),
                                variant=rx.cond(State.current_room == room, "solid", "outline"),
                                width="100%",
                            )
                        ),
                        id="room-list",
                        width="200px",
                    ),
                    rx.hstack(
                        rx.input(
                            placeholder="New room...",
                            value=State.new_room_name,
                            on_change=State.set_new_room_name,
                            id="add-room-input",
                        ),
                        rx.button("Add", on_click=State.add_room, id="add-room-button"),
                    ),
                ),
                rx.divider(orientation="vertical"),
                rx.vstack(
                    rx.heading(State.current_room, id="current-room-title", size="7"),
                    rx.box(
                        rx.cond(
                            State.active_messages.length() > 0,
                            rx.vstack(
                                rx.foreach(
                                    State.active_messages,
                                    lambda msg: rx.hstack(
                                        rx.text(msg.sender, font_weight="bold", width="80px"),
                                        rx.text(msg.content),
                                        width="100%",
                                    )
                                ),
                                rx.cond(
                                    State.streaming_content != "",
                                    rx.hstack(
                                        rx.text("assistant", font_weight="bold", width="80px"),
                                        rx.text(State.streaming_content),
                                        width="100%",
                                    )
                                ),
                                width="100%",
                            ),
                            rx.box(
                                rx.text("No messages yet — say hi!", id="empty-room-placeholder"),
                                rx.cond(
                                    State.streaming_content != "",
                                    rx.hstack(
                                        rx.text("assistant", font_weight="bold", width="80px"),
                                        rx.text(State.streaming_content),
                                        width="100%",
                                    )
                                ),
                            )
                        ),
                        id="message-list",
                        height="400px",
                        overflow_y="auto",
                        width="100%",
                        border="1px solid #ccc",
                        padding="10px",
                    ),
                    rx.form(
                        rx.hstack(
                            rx.input(
                                placeholder="Type a message...",
                                id="message-input",
                                name="message_input",
                                width="100%",
                            ),
                            rx.button("Send", type="submit", id="send-button"),
                        ),
                        on_submit=State.send_message,
                        reset_on_submit=True,
                        width="100%",
                    ),
                    width="100%",
                ),
                width="100%",
                align_items="flex-start",
            ),
            width="100%",
        ),
        padding="20px",
    )

api = FastAPI()

@api.get("/api/rooms")
def api_get_rooms():
    with rx.session() as session:
        rooms = [r.name for r in session.exec(select(Room)).all()]
        return {"rooms": rooms}

@api.post("/api/rooms", status_code=201)
def api_post_rooms(room_data: dict):
    name = room_data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Name is empty")
    with rx.session() as session:
        if session.exec(select(Room).where(Room.name == name)).first():
            raise HTTPException(status_code=409, detail="Room already exists")
        session.add(Room(name=name))
        session.commit()
    return {"name": name}

@api.get("/api/messages")
def api_get_messages(room: str):
    with rx.session() as session:
        messages = session.exec(
            select(Message).where(Message.room == room).order_by(Message.created_at)
        ).all()
        return {
            "room": room,
            "messages": [
                {
                    "id": m.id,
                    "room": m.room,
                    "sender": m.sender,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ]
        }

@api.post("/api/messages")
def api_post_messages(msg_data: dict):
    room = msg_data.get("room")
    content = msg_data.get("content")
    with rx.session() as session:
        if not session.exec(select(Room).where(Room.name == room)).first():
            raise HTTPException(status_code=404, detail="Room not found")
        
        user_msg = Message(room=room, sender="user", content=content)
        session.add(user_msg)
        session.commit()
        session.refresh(user_msg)
        
        chunks = get_assistant_chunks(content)
        full_content = "".join(chunks)
        
        assistant_msg = Message(room=room, sender="assistant", content=full_content)
        session.add(assistant_msg)
        session.commit()
        session.refresh(assistant_msg)
        
        return {
            "user_message": {
                "id": user_msg.id,
                "room": user_msg.room,
                "sender": user_msg.sender,
                "content": user_msg.content,
                "created_at": user_msg.created_at.isoformat(),
            },
            "assistant_chunks": chunks,
            "assistant_message": {
                "id": assistant_msg.id,
                "room": assistant_msg.room,
                "sender": assistant_msg.sender,
                "content": assistant_msg.content,
                "created_at": assistant_msg.created_at.isoformat(),
            }
        }

app = rx.App(api_transformer=api)
app.add_page(index, on_load=State.on_load)
