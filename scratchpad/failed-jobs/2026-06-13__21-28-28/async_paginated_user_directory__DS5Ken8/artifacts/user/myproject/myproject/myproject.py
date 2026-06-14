"""Async Paginated User Directory with Search."""

import math
from typing import List

import reflex as rx
from sqlmodel import select, func, col


# ── Model ────────────────────────────────────────────────────────────────────
class User(rx.Model, table=True):
    """A user in the directory."""

    username: str
    email: str


# ── Query helper (shared with probe.py) ──────────────────────────────────────
async def query_users(
    page: int,
    page_size: int,
    search_query: str,
) -> tuple[list[dict], int]:
    """Return (items_as_dicts, total_matching_count) for the given page/filter.

    This function is the single source of truth for pagination/search logic
    and is reused by ``probe.py`` so both the UI and the CLI exercise the
    same query path.
    """
    offset = (page - 1) * page_size

    async with rx.asession() as session:
        # Build the base filter
        if search_query:
            filter_clause = col(User.username).icontains(search_query)
        else:
            filter_clause = True  # type: ignore[assignment]

        # Total count
        count_stmt = select(func.count()).select_from(User).where(filter_clause)
        total_result = await session.exec(count_stmt)  # type: ignore[arg-type]
        total_users = total_result.one()  # type: ignore[union-attr]

        # Paginated rows
        data_stmt = (
            select(User)
            .where(filter_clause)
            .order_by(User.id)
            .offset(offset)
            .limit(page_size)
        )
        result = await session.exec(data_stmt)  # type: ignore[arg-type]
        rows = result.all()  # type: ignore[union-attr]

        items = [
            {"id": u.id, "username": u.username, "email": u.email}
            for u in rows
        ]

        return items, total_users


# ── State ────────────────────────────────────────────────────────────────────
PAGE_SIZE = 10


class DirectoryState(rx.State):
    """State for the paginated user directory."""

    page: int = 1
    page_size: int = PAGE_SIZE
    search_query: str = ""
    users: list[dict] = []
    total_users: int = 0
    total_pages: int = 0

    @rx.event(background=True)
    async def load_users(self):
        """Background handler: fetch a page of users from the database."""
        # ── Read inputs under the State lock ──────────────────────────────
        async with self:
            current_page = self.page
            current_search = self.search_query

        # ── Database work (no lock held) ─────────────────────────────────
        items, total = await query_users(
            page=current_page,
            page_size=self.page_size,
            search_query=current_search,
        )

        total_pages = math.ceil(total / self.page_size) if total > 0 else 0

        # ── Publish results under the State lock ─────────────────────────
        async with self:
            self.users = items
            self.total_users = total
            self.total_pages = total_pages

    @rx.event
    def set_search(self, value: str):
        """Update the search query and reset to page 1."""
        self.search_query = value
        self.page = 1

    @rx.event
    def prev_page(self):
        """Go to the previous page (minimum 1)."""
        if self.page > 1:
            self.page -= 1

    @rx.event
    def next_page(self):
        """Go to the next page."""
        if self.page < self.total_pages:
            self.page += 1


# ── UI ───────────────────────────────────────────────────────────────────────
def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("User Directory", size="8"),
            # Search input
            rx.input(
                placeholder="Search users…",
                value=DirectoryState.search_query,
                on_change=DirectoryState.set_search,
                width="100%",
            ),
            # User list
            rx.foreach(
                DirectoryState.users,
                lambda user: rx.card(
                    rx.hstack(
                        rx.text(
                            user["username"].to(str),
                            weight="bold",
                        ),
                        rx.text(
                            user["email"].to(str),
                            color="gray",
                        ),
                    ),
                ),
            ),
            # Pagination controls
            rx.hstack(
                rx.button(
                    "Previous",
                    on_click=DirectoryState.prev_page,
                    is_disabled=DirectoryState.page <= 1,
                ),
                rx.text(
                    f"Page {DirectoryState.page} of {DirectoryState.total_pages}",
                ),
                rx.button(
                    "Next",
                    on_click=DirectoryState.next_page,
                    is_disabled=DirectoryState.page >= DirectoryState.total_pages,
                ),
                justify="center",
                width="100%",
                spacing="4",
            ),
            spacing="4",
            align="center",
            min_height="85vh",
        ),
        on_mount=DirectoryState.load_users,
    )


app = rx.App()
app.add_page(index)