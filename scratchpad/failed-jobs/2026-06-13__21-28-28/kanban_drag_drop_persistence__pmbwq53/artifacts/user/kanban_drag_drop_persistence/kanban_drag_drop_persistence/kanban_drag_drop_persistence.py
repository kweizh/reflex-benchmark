"""Kanban board with backend persistence and move API."""

from __future__ import annotations

from typing import List

import reflex as rx
import sqlmodel
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

VALID_COLUMNS = {"TODO", "DOING", "DONE"}


class Card(rx.Model, table=True):
    """A single Kanban card."""

    title: str
    column: str
    position: int


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_DATA = [
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


def seed_db() -> None:
    """Insert seed data if the card table is empty."""
    with rx.session() as sess:
        if sess.exec(sqlmodel.select(Card)).first() is None:
            for card in SEED_DATA:
                sess.add(card)
            sess.commit()


# ---------------------------------------------------------------------------
# FastAPI move endpoint
# ---------------------------------------------------------------------------

api_app = FastAPI()


class MoveRequest(BaseModel):
    card_id: int
    target_column: str
    target_position: int


@api_app.post("/api/cards/move")
def move_card(req: MoveRequest):
    if req.target_column not in VALID_COLUMNS:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid target_column", "ok": False},
        )

    with rx.session() as sess:
        card = sess.get(Card, req.card_id)
        if card is None:
            return JSONResponse(
                status_code=404,
                content={"error": "card not found", "ok": False},
            )

        src_col = card.column
        dst_col = req.target_column

        if src_col == dst_col:
            # Moving within same column
            cards_in_col = list(
                sess.exec(
                    sqlmodel.select(Card)
                    .where(Card.column == dst_col)
                    .order_by(Card.position)
                ).all()
            )
            cards_in_col.remove(card)
            pos = min(req.target_position, len(cards_in_col))
            cards_in_col.insert(pos, card)
            for i, c in enumerate(cards_in_col):
                c.position = i
                sess.add(c)
        else:
            # Moving to a different column
            src_cards = list(
                sess.exec(
                    sqlmodel.select(Card)
                    .where(Card.column == src_col)
                    .order_by(Card.position)
                ).all()
            )
            src_cards.remove(card)

            dst_cards = list(
                sess.exec(
                    sqlmodel.select(Card)
                    .where(Card.column == dst_col)
                    .order_by(Card.position)
                ).all()
            )

            pos = min(req.target_position, len(dst_cards))

            card.column = dst_col
            dst_cards.insert(pos, card)

            for i, c in enumerate(src_cards):
                c.position = i
                sess.add(c)

            for i, c in enumerate(dst_cards):
                c.position = i
                sess.add(c)

        sess.commit()

    return {"ok": True}


# ---------------------------------------------------------------------------
# Reflex state
# ---------------------------------------------------------------------------

class KanbanState(rx.State):
    """State for the Kanban board."""

    todo_cards: List[Card] = []
    doing_cards: List[Card] = []
    done_cards: List[Card] = []

    def load_cards(self) -> None:
        """Load all cards from DB grouped by column."""
        with rx.session() as sess:
            all_cards = sess.exec(
                sqlmodel.select(Card).order_by(Card.column, Card.position)
            ).all()
            self.todo_cards = [c for c in all_cards if c.column == "TODO"]
            self.doing_cards = [c for c in all_cards if c.column == "DOING"]
            self.done_cards = [c for c in all_cards if c.column == "DONE"]


# ---------------------------------------------------------------------------
# UI rendering helpers
# ---------------------------------------------------------------------------

def card_component(card: Card) -> rx.Component:
    """Render a single card."""
    return rx.box(
        rx.text(card.title, font_size="0.9rem", font_weight="medium"),
        padding="0.5rem 0.75rem",
        border_radius="0.375rem",
        background_color="var(--gray-3)",
        border="1px solid var(--gray-5)",
        margin_bottom="0.25rem",
    )


def todo_column() -> rx.Component:
    """Render the TODO column."""
    return rx.box(
        rx.heading("TODO", size="4", margin_bottom="0.75rem"),
        rx.foreach(KanbanState.todo_cards, card_component),
        flex="1",
        min_width="200px",
        padding="1rem",
        border_radius="0.5rem",
        background_color="var(--gray-2)",
    )


def doing_column() -> rx.Component:
    """Render the DOING column."""
    return rx.box(
        rx.heading("DOING", size="4", margin_bottom="0.75rem"),
        rx.foreach(KanbanState.doing_cards, card_component),
        flex="1",
        min_width="200px",
        padding="1rem",
        border_radius="0.5rem",
        background_color="var(--gray-2)",
    )


def done_column() -> rx.Component:
    """Render the DONE column."""
    return rx.box(
        rx.heading("DONE", size="4", margin_bottom="0.75rem"),
        rx.foreach(KanbanState.done_cards, card_component),
        flex="1",
        min_width="200px",
        padding="1rem",
        border_radius="0.5rem",
        background_color="var(--gray-2)",
    )


# ---------------------------------------------------------------------------
# Page & App
# ---------------------------------------------------------------------------

def index() -> rx.Component:
    """The main Kanban board page."""
    return rx.container(
        rx.hstack(
            todo_column(),
            doing_column(),
            done_column(),
            spacing="4",
            align_items="flex_start",
            width="100%",
        ),
        on_mount=KanbanState.load_cards,
    )


# Create the Reflex app with the FastAPI transformer
app = rx.App(api_transformer=api_app)
app.add_page(index)

# Register seed_db as a lifespan task so it runs on app startup
app.register_lifespan_task(seed_db)