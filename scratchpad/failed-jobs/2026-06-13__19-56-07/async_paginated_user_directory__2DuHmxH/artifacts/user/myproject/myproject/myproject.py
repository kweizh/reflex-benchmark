import reflex as rx
from sqlmodel import select, func, or_
import asyncio
import math
from typing import List

class User(rx.Model, table=True):
    username: str
    email: str

def get_query_results(search_query: str, page: int, page_size: int):
    offset = (page - 1) * page_size
    
    # Base query for filtering
    query = select(User)
    if search_query:
        # Case-insensitive contains-match on username
        query = query.where(User.username.ilike(f"%{search_query}%"))
    
    # Count query
    count_query = select(func.count()).select_from(query.subquery())
    
    # Paginated query
    paginated_query = query.order_by(User.id.asc()).offset(offset).limit(page_size)
    
    return count_query, paginated_query

class State(rx.State):
    users: List[User] = []
    total_users: int = 0
    total_pages: int = 0
    page: int = 1
    page_size: int = 10
    search_query: str = ""
    is_loading: bool = False

    @rx.event(background=True)
    async def fetch_users(self):
        async with self:
            if self.is_loading:
                return
            self.is_loading = True
            search_query = self.search_query
            page = self.page
            page_size = self.page_size

        count_query, paginated_query = get_query_results(search_query, page, page_size)
        
        async with rx.asession() as session:
            try:
                total_users = (await session.exec(count_query)).one()
                users = (await session.exec(paginated_query)).all()
            except Exception:
                # Fallback if rx.asession() fails due to config issues in background task
                from sqlalchemy.ext.asyncio import create_async_engine
                from sqlmodel.ext.asyncio.session import AsyncSession
                engine = create_async_engine("sqlite+aiosqlite:///reflex.db")
                async with AsyncSession(engine) as session2:
                    total_users = (await session2.exec(count_query)).one()
                    users = (await session2.exec(paginated_query)).all()
            
        async with self:
            self.users = users
            self.total_users = total_users
            if self.total_users > 0:
                self.total_pages = math.ceil(self.total_users / self.page_size)
            else:
                self.total_pages = 0
            self.is_loading = False

    def set_search_query(self, query: str):
        self.search_query = query
        self.page = 1
        return State.fetch_users

    def next_page(self):
        if self.page < self.total_pages:
            self.page += 1
            return State.fetch_users

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            return State.fetch_users

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("User Directory", size="8"),
            rx.input(
                placeholder="Search by username...",
                value=State.search_query,
                on_change=State.set_search_query,
                width="100%",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("ID"),
                        rx.table.column_header_cell("Username"),
                        rx.table.column_header_cell("Email"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        State.users,
                        lambda user: rx.table.row(
                            rx.table.cell(user.id),
                            rx.table.cell(user.username),
                            rx.table.cell(user.email),
                        ),
                    )
                ),
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    "Previous",
                    on_click=State.prev_page,
                    disabled=State.page <= 1,
                ),
                rx.text(f"Page {State.page} of {State.total_pages}"),
                rx.button(
                    "Next",
                    on_click=State.next_page,
                    disabled=State.page >= State.total_pages,
                ),
                justify="between",
                width="100%",
            ),
            rx.text(f"Total Users: {State.total_users}"),
            spacing="4",
            padding="4",
            on_mount=State.fetch_users,
        ),
        center_x=True,
    )

app = rx.App()
app.add_page(index)
