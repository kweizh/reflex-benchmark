import reflex as rx
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class Card(rx.Model, table=True):
    title: str
    column: str
    position: int

class MoveRequest(BaseModel):
    card_id: int
    target_column: str
    target_position: int

class State(rx.State):
    cards: List[Card] = []

    def load_cards(self):
        with rx.session() as session:
            # Seed if empty
            if session.exec(Card.select()).first() is None:
                initial_cards = [
                    Card(title="Write spec", column="TODO", position=0),
                    Card(title="Draft API", column="TODO", position=1),
                    Card(title="Review PR", column="TODO", position=2),
                    Card(title="Build UI", column="DOING", position=0),
                    Card(title="Wire DB", column="DOING", position=1),
                    Card(title="Add tests", column="DOING", position=2),
                    Card(title="Setup repo", column="DONE", position=0),
                    Card(title="Pick stack", column="DONE", position=1),
                    Card(title="Kickoff", column="DONE", position=2),
                ]
                session.add_all(initial_cards)
                session.commit()
            
            self.cards = session.exec(
                Card.select().order_by(Card.column, Card.position)
            ).all()

    @rx.var
    def todo_cards(self) -> List[Card]:
        return [c for c in self.cards if c.column == "TODO"]

    @rx.var
    def doing_cards(self) -> List[Card]:
        return [c for c in self.cards if c.column == "DOING"]

    @rx.var
    def done_cards(self) -> List[Card]:
        return [c for c in self.cards if c.column == "DONE"]

def move_card_logic(card_id: int, target_column: str, target_position: int):
    if target_column not in ["TODO", "DOING", "DONE"]:
        raise HTTPException(status_code=400, detail="Invalid target column")

    with rx.session() as session:
        card = session.get(Card, card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        source_column = card.column
        
        # Get all cards in source and target columns
        if source_column == target_column:
            # Moving within the same column
            cards = session.exec(
                Card.select()
                .where(Card.column == source_column)
                .order_by(Card.position)
            ).all()
            
            # Remove the card from its current position
            cards = [c for c in cards if c.id != card_id]
            # Insert at target position
            target_pos = max(0, min(target_position, len(cards)))
            cards.insert(target_pos, card)
            
            # Renumber
            for i, c in enumerate(cards):
                c.position = i
        else:
            # Moving between columns
            source_cards = session.exec(
                Card.select()
                .where(Card.column == source_column)
                .order_by(Card.position)
            ).all()
            target_cards = session.exec(
                Card.select()
                .where(Card.column == target_column)
                .order_by(Card.position)
            ).all()
            
            # Remove from source
            source_cards = [c for c in source_cards if c.id != card_id]
            # Renumber source
            for i, c in enumerate(source_cards):
                c.position = i
            
            # Insert into target
            target_pos = max(0, min(target_position, len(target_cards)))
            target_cards.insert(target_pos, card)
            card.column = target_column
            # Renumber target
            for i, c in enumerate(target_cards):
                c.position = i
        
        session.commit()
    return {"ok": True}

def api_transformer(app) -> FastAPI:
    custom_api = FastAPI()
    @custom_api.post("/cards/move")
    async def move_card(request: MoveRequest):
        return move_card_logic(request.card_id, request.target_column, request.target_position)
    app.mount("/api", custom_api)
    return app

def card_view(card: Card):
    return rx.box(
        rx.text(card.title),
        border="1px solid #ccc",
        padding="10px",
        margin="5px",
        border_radius="5px",
        background_color="white",
    )

def column_view(name: str, cards: List[Card]):
    return rx.vstack(
        rx.heading(name, size="4"),
        rx.foreach(cards, card_view),
        width="300px",
        padding="10px",
        background_color="#f4f4f4",
        border_radius="8px",
        min_height="500px",
        align_items="stretch",
    )

def index():
    return rx.center(
        rx.hstack(
            column_view("TODO", State.todo_cards),
            column_view("DOING", State.doing_cards),
            column_view("DONE", State.done_cards),
            align_items="flex-start",
            spacing="4",
        ),
        padding_top="50px",
    )

app = rx.App(
    api_transformer=api_transformer,
)
app.add_page(index, on_load=State.load_cards)
