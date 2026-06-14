import reflex as rx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from typing import List

from rxconfig import config

class Card(rx.Model, table=True):
    title: str
    column: str
    position: int

class MoveRequest(BaseModel):
    card_id: int
    target_column: str
    target_position: int

api = FastAPI()

@api.post("/api/cards/move")
def move_card(request: MoveRequest):
    if request.target_column not in ["TODO", "DOING", "DONE"]:
        raise HTTPException(status_code=400, detail="Invalid target column")
    
    with rx.session() as session:
        card = session.get(Card, request.card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        source_column = card.column
        
        # Get all cards in source column ordered by position
        source_cards = session.exec(select(Card).where(Card.column == source_column).order_by(Card.position)).all()
        # Remove the card from source_cards list
        source_cards = [c for c in source_cards if c.id != card.id]
        
        if source_column == request.target_column:
            target_cards = source_cards
        else:
            target_cards = session.exec(select(Card).where(Card.column == request.target_column).order_by(Card.position)).all()
        
        # Clamp target position
        target_pos = max(0, min(request.target_position, len(target_cards)))
        
        # Insert the card into target_cards
        target_cards.insert(target_pos, card)
        card.column = request.target_column
        
        # Re-number source column if different from target
        if source_column != request.target_column:
            for i, c in enumerate(source_cards):
                c.position = i
                session.add(c)
        
        # Re-number target column
        for i, c in enumerate(target_cards):
            c.position = i
            session.add(c)
            
        session.commit()
        return {"ok": True}

class State(rx.State):
    """The app state."""
    cards: List[Card] = []

    def load_cards(self):
        with rx.session() as session:
            self.cards = session.exec(select(Card).order_by(Card.position)).all()

    @rx.var(cache=True)
    def todo_cards(self) -> List[Card]:
        return [c for c in self.cards if c.column == "TODO"]

    @rx.var(cache=True)
    def doing_cards(self) -> List[Card]:
        return [c for c in self.cards if c.column == "DOING"]

    @rx.var(cache=True)
    def done_cards(self) -> List[Card]:
        return [c for c in self.cards if c.column == "DONE"]


def render_card(card: Card):
    return rx.box(
        rx.text(card.title),
        padding="2",
        margin_bottom="2",
        border="1px solid #ccc",
        border_radius="4px",
        background_color="white",
    )

def render_column(title: str, cards: List[Card]):
    return rx.vstack(
        rx.heading(title, size="5"),
        rx.vstack(
            rx.foreach(cards, render_card),
            width="100%",
            min_height="200px",
            padding="2",
            border="1px solid #eee",
            border_radius="4px",
            background_color="#f9f9f9",
        ),
        width="30%",
    )

def index() -> rx.Component:
    return rx.container(
        rx.hstack(
            render_column("TODO", State.todo_cards),
            render_column("DOING", State.doing_cards),
            render_column("DONE", State.done_cards),
            justify="between",
            align="start",
            width="100%",
            padding_top="10",
        ),
        on_mount=State.load_cards
    )

app = rx.App(api_transformer=api)
app.add_page(index)

from sqlalchemy.exc import OperationalError

def seed_db():
    try:
        with rx.session() as session:
            count = session.exec(select(Card)).all()
            if not count:
                seed_data = [
                    Card(column="TODO", position=0, title="Write spec"),
                    Card(column="TODO", position=1, title="Draft API"),
                    Card(column="TODO", position=2, title="Review PR"),
                    Card(column="DOING", position=0, title="Build UI"),
                    Card(column="DOING", position=1, title="Wire DB"),
                    Card(column="DOING", position=2, title="Add tests"),
                    Card(column="DONE", position=0, title="Setup repo"),
                    Card(column="DONE", position=1, title="Pick stack"),
                    Card(column="DONE", position=2, title="Kickoff"),
                ]
                for c in seed_data:
                    session.add(c)
                session.commit()
    except OperationalError:
        pass

# Run seed on startup
seed_db()
