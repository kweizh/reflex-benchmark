"""Reflex Async Paginated User Directory."""

import reflex as rx
from sqlmodel import select


class User(rx.Model, table=True):
    """User database model."""

    username: str
    email: str


# Seed data – 50 distinct users
SEED_USERS: list[dict[str, str]] = [
    {"username": f"user{i:03d}", "email": f"user{i:03d}@example.com"}
    for i in range(1, 51)
]


class PaginatedState(rx.State):
    """State for paginated user directory."""

    page: int = 1
    page_size: int = 10
    users: list[User] = []

    @rx.event
    async def load_page(self):
        """Seed the database if empty, then fetch the first page."""
        async with rx.asession() as asession:
            result = await asession.execute(select(User))
            existing = result.all()
            if not existing:
                for user_data in SEED_USERS:
                    user = User(**user_data)
                    asession.add(user)
                await asession.commit()
        return PaginatedState.fetch_page

    @rx.event(background=True)
    async def fetch_page(self):
        """Background event to fetch a page of users from the database."""
        async with rx.asession() as asession:
            offset = (self.page - 1) * self.page_size
            stmt = select(User).offset(offset).limit(self.page_size)
            result = await asession.execute(stmt)
            rows = [row[0] for row in result.all()]
        async with self:
            self.users = rows

    async def prev_page(self):
        """Go to the previous page and re-fetch."""
        if self.page > 1:
            self.page -= 1
        return PaginatedState.fetch_page

    async def next_page(self):
        """Go to the next page and re-fetch."""
        self.page += 1
        return PaginatedState.fetch_page


def index() -> rx.Component:
    """The main index page showing the user directory."""
    return rx.container(
        rx.vstack(
            rx.heading("User Directory", size="8"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Username"),
                        rx.table.column_header_cell("Email"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        PaginatedState.users,
                        lambda user: rx.table.row(
                            rx.table.cell(user.username),
                            rx.table.cell(user.email),
                        ),
                    )
                ),
            ),
            rx.hstack(
                rx.button(
                    "Prev",
                    on_click=PaginatedState.prev_page,
                ),
                rx.text(f"Page {PaginatedState.page}"),
                rx.button(
                    "Next",
                    on_click=PaginatedState.next_page,
                ),
                spacing="4",
                align="center",
            ),
            spacing="5",
            align="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index, on_load=PaginatedState.load_page)