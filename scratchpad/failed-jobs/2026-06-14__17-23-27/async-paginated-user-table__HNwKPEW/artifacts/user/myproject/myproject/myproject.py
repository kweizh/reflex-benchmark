"""Paginated User Directory - Reflex Application."""

import asyncio

import reflex as rx
import sqlmodel


class User(rx.Model, table=True):
    """A user in the directory."""

    username: str
    email: str


class State(rx.State):
    """The app state with pagination."""

    page: int = 1
    page_size: int = 10
    users: list[User] = []

    async def _seed_users(self) -> bool:
        """Seed the user table with sample data if empty.

        Returns:
            True if seeding was performed, False otherwise.
        """
        async with rx.asession() as asession:
            result = await asession.execute(sqlmodel.select(User).limit(1))
            if result.first() is not None:
                return False

            sample_users = [
                User(username=f"user_{i:03d}", email=f"user_{i:03d}@example.com")
                for i in range(1, 51)
            ]
            asession.add_all(sample_users)
            await asession.commit()
            return True

    @rx.event(background=True)
    async def fetch_page(self):
        """Fetch the current page of users from the database."""
        async with rx.asession() as asession:
            offset = (self.page - 1) * self.page_size
            stmt = sqlmodel.select(User).offset(offset).limit(self.page_size)
            result = await asession.execute(stmt)
            rows = [row[0] for row in result.all()]

            async with self:
                self.users = rows

    @rx.event
    async def on_load(self):
        """Called when the page loads. Seed data and fetch first page."""
        await self._seed_users()
        yield self.fetch_page()

    @rx.event
    async def prev_page(self):
        """Go to the previous page."""
        if self.page > 1:
            self.page -= 1
        yield self.fetch_page()

    @rx.event
    async def next_page(self):
        """Go to the next page."""
        self.page += 1
        yield self.fetch_page()


def index() -> rx.Component:
    """Render the user directory page."""
    return rx.container(
        rx.vstack(
            rx.heading("User Directory", size="8"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Username"),
                        rx.table.column_header_cell("Email"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        State.users,
                        lambda user: rx.table.row(
                            rx.table.cell(user.username),
                            rx.table.cell(user.email),
                        ),
                    ),
                ),
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    "Prev",
                    on_click=State.prev_page,
                    disabled=State.page <= 1,
                ),
                rx.text(f"Page {State.page}"),
                rx.button(
                    "Next",
                    on_click=State.next_page,
                ),
                spacing="4",
            ),
            spacing="6",
            align="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index, route="/", on_load=State.on_load)
