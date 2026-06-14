"""Reflex application: Paginated, searchable user directory."""

import asyncio

import reflex as rx

from .query import query_users
from .seeder import seed


class State(rx.State):
    """Application state for the user directory."""

    page: int = 1
    page_size: int = 10
    search_query: str = ""
    users: list[dict] = []
    total_users: int = 0
    total_pages: int = 0

    @rx.event(background=True)
    async def load_users(self):
        """Background handler: fetch users with current search/pagination params."""
        # Read inputs under the state lock
        async with self:
            search = self.search_query
            p = self.page
            ps = self.page_size

        # Query the database outside the lock
        result = await query_users(page=p, search_query=search)

        # Publish results under the state lock
        async with self:
            self.users = result["items"]
            self.total_users = result["total_users"]
            self.total_pages = result["total_pages"]

    @rx.event
    async def set_search(self, value: str):
        """Update search query, reset to page 1, and reload."""
        self.search_query = value
        self.page = 1
        return State.load_users  # type: ignore[return-type]

    @rx.event
    async def go_previous(self):
        """Go to the previous page if possible."""
        if self.page > 1:
            self.page -= 1
            return State.load_users  # type: ignore[return-type]

    @rx.event
    async def go_next(self):
        """Go to the next page if possible."""
        if self.page < self.total_pages:
            self.page += 1
            return State.load_users  # type: ignore[return-type]


def index() -> rx.Component:
    """The main user directory page."""
    return rx.container(
        rx.vstack(
            rx.heading("User Directory", size="8"),
            rx.hstack(
                rx.input(
                    placeholder="Search by username...",
                    value=State.search_query,
                    on_change=State.set_search,
                    width="300px",
                ),
                rx.button(
                    "Previous",
                    on_click=State.go_previous,
                    disabled=(State.page <= 1),
                ),
                rx.button(
                    "Next",
                    on_click=State.go_next,
                    disabled=(State.page >= State.total_pages),
                ),
                rx.text(
                    rx.cond(
                        State.total_pages > 0,
                        f"Page {State.page} of {State.total_pages}",
                        "Page 0 of 0",
                    ),
                ),
                spacing="4",
                align="center",
            ),
            rx.divider(),
            rx.foreach(
                State.users,
                lambda user: rx.card(
                    rx.vstack(
                        rx.text(user["username"], font_weight="bold"),
                        rx.text(user["email"], color="gray"),
                        align="start",
                        spacing="1",
                    ),
                    width="100%",
                ),
            ),
            spacing="4",
            width="100%",
            padding="2em",
        ),
        max_width="800px",
    )


async def _startup_seed():
    """Seed the database on startup."""
    await seed()


app = rx.App()
app.add_page(index, on_load=State.load_users)

# Register the seeding as a startup event
app.register_lifespan_task(_startup_seed)
