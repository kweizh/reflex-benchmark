"""Paginated User Directory – Reflex application."""

import reflex as rx
import sqlmodel

from rxconfig import config


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------


class User(rx.Model, table=True):
    """A user record stored in the SQLite database."""

    username: str
    email: str


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_USERS: list[dict] = [
    {"username": f"user{i:02d}", "email": f"user{i:02d}@example.com"}
    for i in range(1, 61)
]


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


class State(rx.State):
    """Holds pagination state and the current page of users."""

    page: int = 1
    page_size: int = 10
    users: list[User] = []

    @rx.event(background=True)
    async def seed_and_fetch(self):
        """Seed the database on first load, then fetch the first page."""
        async with rx.asession() as asession:
            # Seed if empty
            result = await asession.execute(sqlmodel.select(User).limit(1))
            first = result.first()
            if first is None:
                for data in SEED_USERS:
                    asession.add(User(**data))
                await asession.commit()

            # Fetch the current page
            async with self:
                offset = (self.page - 1) * self.page_size
                page_size = self.page_size

            stmt = sqlmodel.select(User).offset(offset).limit(page_size)
            result = await asession.execute(stmt)
            rows = [row[0] for row in result.all()]

        async with self:
            self.users = rows

    @rx.event(background=True)
    async def fetch_page(self):
        """Load one page of users from the database (background event)."""
        async with rx.asession() as asession:
            async with self:
                offset = (self.page - 1) * self.page_size
                page_size = self.page_size

            stmt = sqlmodel.select(User).offset(offset).limit(page_size)
            result = await asession.execute(stmt)
            rows = [row[0] for row in result.all()]

        async with self:
            self.users = rows

    @rx.event
    async def prev_page(self):
        """Go to the previous page (minimum page 1)."""
        if self.page > 1:
            self.page -= 1
        yield State.fetch_page

    @rx.event
    async def next_page(self):
        """Go to the next page."""
        self.page += 1
        yield State.fetch_page


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------


def user_row(user: User) -> rx.Component:
    """Render a single table row for a user."""
    return rx.table.row(
        rx.table.cell(user.username),
        rx.table.cell(user.email),
    )


def index() -> rx.Component:
    """The main page: a table of users with Prev/Next pagination controls."""
    return rx.container(
        rx.vstack(
            rx.heading("User Directory", size="7"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Username"),
                        rx.table.column_header_cell("Email"),
                    )
                ),
                rx.table.body(
                    rx.foreach(State.users, user_row),
                ),
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    "Prev",
                    on_click=State.prev_page,
                    disabled=State.page <= 1,
                ),
                rx.text("Page ", State.page),
                rx.button(
                    "Next",
                    on_click=State.next_page,
                ),
                spacing="4",
                justify="center",
            ),
            spacing="5",
            align="center",
            padding="4",
        ),
    )


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

app = rx.App()
app.add_page(index, route="/", on_load=State.seed_and_fetch)
