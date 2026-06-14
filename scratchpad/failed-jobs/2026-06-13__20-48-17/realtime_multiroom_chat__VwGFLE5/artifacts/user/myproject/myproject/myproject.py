import reflex as rx
import asyncio
from datetime import datetime
from sqlmodel import Field, select
from typing import List
from fastapi import FastAPI, Response, status
from pydantic import BaseModel

class Room(rx.Model, table=True):
    name: str = Field(unique=True, index=True)

class Message(rx.Model, table=True):
    room: str = Field(index=True)
    sender: str
    content: str
    created_at: str

def generate_chunks(content: str) -> List[str]:
    words = f"Hello! I am an assistant. You said: {content}".split(" ")
    chunks = []
    for i, word in enumerate(words):
        if i > 0:
            chunks.append(" " + word)
        else:
            chunks.append(word)
    if len(chunks) < 5:
        text = f"Hello! I am an assistant. You said: {content}"
        chunks = [text[i:i+2] for i in range(0, len(text), 2)]
        if len(chunks) < 5:
            chunks = ["a", "b", "c", "d", "e"]
    return chunks

class State(rx.State):
    current_room: str = "general"
    rooms: List[str] = []
    current_messages: List[Message] = []
    new_room_name: str = ""
    new_message_content: str = ""

    def set_new_room_name(self, name: str):
        self.new_room_name = name

    def set_new_message_content(self, content: str):
        self.new_message_content = content
    
    def on_load(self):
        with rx.session() as session:
            rooms_in_db = session.exec(select(Room)).all()
            if not rooms_in_db:
                session.add(Room(name="general"))
                session.add(Room(name="random"))
                session.commit()
                rooms_in_db = session.exec(select(Room)).all()
            
            self.rooms = [r.name for r in rooms_in_db]
            if self.current_room not in self.rooms and self.rooms:
                self.current_room = self.rooms[0]
            
        self.load_messages()
        
    def load_messages(self):
        with rx.session() as session:
            messages = session.exec(select(Message).where(Message.room == self.current_room).order_by(Message.created_at)).all()
            self.current_messages = messages

    def select_room(self, room: str):
        self.current_room = room
        self.load_messages()

    def add_room(self):
        if not self.new_room_name:
            return
        with rx.session() as session:
            existing = session.exec(select(Room).where(Room.name == self.new_room_name)).first()
            if not existing:
                session.add(Room(name=self.new_room_name))
                session.commit()
                self.rooms.append(self.new_room_name)
        self.new_room_name = ""

    async def send_message(self):
        if not self.new_message_content:
            return
        
        content = self.new_message_content
        self.new_message_content = ""
        
        user_msg = Message(
            room=self.current_room,
            sender="user",
            content=content,
            created_at=datetime.now().isoformat()
        )
        with rx.session() as session:
            session.add(user_msg)
            session.commit()
            session.refresh(user_msg)
        
        self.load_messages()
        yield
        
        chunks = generate_chunks(content)
        
        assistant_msg = Message(
            room=self.current_room,
            sender="assistant",
            content="",
            created_at=datetime.now().isoformat()
        )
        self.current_messages.append(assistant_msg)
        
        for chunk in chunks:
            await asyncio.sleep(0.1)
            assistant_msg.content += chunk
            self.current_messages[-1] = assistant_msg
            yield
        
        with rx.session() as session:
            session.add(assistant_msg)
            session.commit()
        self.load_messages()

def index() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.heading("Rooms"),
            rx.vstack(
                rx.foreach(
                    State.rooms,
                    lambda room: rx.button(
                        room,
                        on_click=State.select_room(room)
                    )
                ),
                id="room-list"
            ),
            rx.input(
                id="add-room-input",
                placeholder="New room",
                value=State.new_room_name,
                on_change=State.set_new_room_name
            ),
            rx.button(
                "Add Room",
                id="add-room-button",
                on_click=State.add_room
            )
        ),
        rx.vstack(
            rx.heading(State.current_room, id="current-room-title"),
            rx.cond(
                State.current_messages.length() == 0,
                rx.text("No messages yet — say hi!", id="empty-room-placeholder"),
                rx.vstack(
                    rx.foreach(
                        State.current_messages,
                        lambda msg: rx.text(msg.sender + ": " + msg.content)
                    ),
                    id="message-list"
                )
            ),
            rx.hstack(
                rx.input(
                    id="message-input",
                    value=State.new_message_content,
                    on_change=State.set_new_message_content
                ),
                rx.button(
                    "Send",
                    id="send-button",
                    on_click=State.send_message
                )
            )
        )
    )

api = FastAPI()

@api.get("/api/rooms")
def api_get_rooms():
    with rx.session() as session:
        rooms = session.exec(select(Room)).all()
        return {"rooms": [r.name for r in rooms]}

class RoomPayload(BaseModel):
    name: str

@api.post("/api/rooms")
def api_post_rooms(payload: RoomPayload, response: Response):
    name = payload.name
    if not name:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Name is empty"}
    with rx.session() as session:
        existing = session.exec(select(Room).where(Room.name == name)).first()
        if existing:
            response.status_code = status.HTTP_409_CONFLICT
            return {"error": "Room exists"}
        session.add(Room(name=name))
        session.commit()
        response.status_code = status.HTTP_201_CREATED
        return {"name": name}

@api.get("/api/messages")
def api_get_messages(room: str):
    with rx.session() as session:
        messages = session.exec(select(Message).where(Message.room == room).order_by(Message.created_at)).all()
        return {"room": room, "messages": [{"id": m.id, "room": m.room, "sender": m.sender, "content": m.content, "created_at": m.created_at} for m in messages]}

class MessagePayload(BaseModel):
    room: str
    content: str

@api.post("/api/messages")
def api_post_messages(payload: MessagePayload, response: Response):
    room = payload.room
    content = payload.content
    with rx.session() as session:
        existing = session.exec(select(Room).where(Room.name == room)).first()
        if not existing:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "Room not found"}
        
        user_msg = Message(
            room=room,
            sender="user",
            content=content,
            created_at=datetime.now().isoformat()
        )
        session.add(user_msg)
        session.commit()
        session.refresh(user_msg)
        
        chunks = generate_chunks(content)
        
        assistant_msg = Message(
            room=room,
            sender="assistant",
            content="".join(chunks),
            created_at=datetime.now().isoformat()
        )
        session.add(assistant_msg)
        session.commit()
        session.refresh(assistant_msg)
        
        return {
            "user_message": {"id": user_msg.id, "room": user_msg.room, "sender": user_msg.sender, "content": user_msg.content, "created_at": user_msg.created_at},
            "assistant_chunks": chunks,
            "assistant_message": {"id": assistant_msg.id, "room": assistant_msg.room, "sender": assistant_msg.sender, "content": assistant_msg.content, "created_at": assistant_msg.created_at}
        }

app = rx.App(api_transformer=api)
app.add_page(index, on_load=State.on_load)
