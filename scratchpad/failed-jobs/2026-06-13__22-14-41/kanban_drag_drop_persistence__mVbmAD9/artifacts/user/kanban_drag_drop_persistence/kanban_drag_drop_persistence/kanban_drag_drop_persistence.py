"""Kanban board with backend persistence and move API."""

import reflex as rx
from sqlmodel import select, func
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Card(rx.Model, table=True):
    """A kanban card persisted in SQLite."""

    title: str
    column: str  # one of TODO, DOING, DONE
    position: int  # 0-based index inside its column


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_CARDS = [
    ("TODO", 0, "Write spec"),
    ("TODO", 1, "Draft API"),
    ("TODO", 2, "Review PR"),
    ("DOING", 0, "Build UI"),
    ("DOING", 1, "Wire DB"),
    ("DOING", 2, "Add tests"),
    ("DONE", 0, "Setup repo"),
    ("DONE", 1, "Pick stack"),
    ("DONE", 2, "Kickoff"),
]

VALID_COLUMNS = {"TODO", "DOING", "DONE"}


def seed_database():
    """Insert seed cards if the database is empty (tables must already exist)."""
    with rx.session() as session:
        count = session.exec(select(func.count()).select_from(Card)).one()
        if count == 0:
            for col, pos, title in SEED_CARDS:
                session.add(Card(title=title, column=col, position=pos))
            session.commit()


# ---------------------------------------------------------------------------
# FastAPI move endpoint
# ---------------------------------------------------------------------------

class MoveRequest(BaseModel):
    card_id: int
    target_column: str
    target_position: int


def handle_move(req: MoveRequest):
    """Move a card to a target column/position, renormalising both columns."""
    if req.target_column not in VALID_COLUMNS:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": f"Invalid column: {req.target_column}"},
        )

    with rx.session() as session:
        card = session.get(Card, req.card_id)
        if card is None:
            return JSONResponse(status_code=404, content={"ok": False})

        source_column = card.column
        target_column = req.target_column
        target_pos = req.target_position

        # Remove from source column
        session.expunge(card)

        if source_column == target_column:
            # Same column move: remove from current list, re-insert at target
            siblings = session.exec(
                select(Card)
                .where(Card.column == source_column)
                .order_by(Card.position)
            ).all()
            siblings.remove(card)
            target_pos = max(0, min(target_pos, len(siblings)))
            siblings.insert(target_pos, card)

            # Renormalize
            for idx, c in enumerate(siblings):
                c.position = idx
        else:
            # Cross-column move
            source_cards = session.exec(
                select(Card)
                .where(Card.column == source_column)
                .order_by(Card.position)
            ).all()
            source_cards.remove(card)

            target_cards = session.exec(
                select(Card)
                .where(Card.column == target_column)
                .order_by(Card.position)
            ).all()
            target_pos = max(0, min(target_pos, len(target_cards)))
            target_cards.insert(target_pos, card)

            card.column = target_column

            # Renormalize source column
            for idx, c in enumerate(source_cards):
                c.position = idx

            # Renormalize target column
            for idx, c in enumerate(target_cards):
                c.position = idx

        # Re-add card to session and commit
        session.add(card)
        session.commit()

    return {"ok": True}


def make_fastapi_app() -> FastAPI:
    """Build the FastAPI app that will be mounted via api_transformer."""
    api = FastAPI()

    @api.post("/api/cards/move")
    def move_card(req: MoveRequest):
        return handle_move(req)

    return api


# ---------------------------------------------------------------------------
# Reflex page
# ---------------------------------------------------------------------------

class KanbanState(rx.State):
    """Holds the current cards loaded from the DB."""

    cards: list[Card] = []

    def load_cards(self):
        """Reload cards from the database."""
        with rx.session() as session:
            self.cards = list(
                session.exec(select(Card).order_by(Card.column, Card.position)).all()
            )

    def on_load(self):
        """Called when the page loads."""
        self.load_cards()


def card_item(card: Card) -> rx.Component:
    """Render a single card."""
    return rx.box(
        rx.text(card.title, font_weight="bold"),
        padding="0.75rem",
        margin="0.5rem 0",
        border_radius="0.5rem",
        background_color="var(--gray-3)",
        border="1px solid var(--gray-6)",
    )


def column_view(column_name: str, cards: list[Card]) -> rx.Component:
    """Render one column with its cards."""
    return rx.box(
        rx.heading(column_name, size="5", margin_bottom="1rem", text_align="center"),
        rx.foreach(
            cards,
            card_item,
        ),
        padding="1rem",
        border_radius="0.5rem",
        background_color="var(--gray-2)",
        border="1px solid var(--gray-5)",
        min_height="300px",
        width="300px",
    )


def index() -> rx.Component:
    """The Kanban board page."""
    return rx.container(
        rx.heading("Kanban Board", size="8", text_align="center", margin_bottom="2rem"),
        rx.hstack(
            column_view(
                "TODO",
                KanbanState.cards.where(lambda c: c.column == "TODO"),
            ),
            column_view(
                "DOING",
                KanbanState.cards.where(lambda c: c.column == "DOING"),
            ),
            column_view(
                "DONE",
                KanbanState.cards.where(lambda c: c.column == "DONE"),
            ),
            spacing="4",
            justify="center",
            align_items="start",
        ),
        padding_top="2rem",
        on_mount=KanbanState.on_load,
    )


# ---------------------------------------------------------------------------
# App entry point
# ---------------------------------------------------------------------------

app = rx.App(
    api_transformer=make_fastapi_app(),
)
app.add_page(index)
