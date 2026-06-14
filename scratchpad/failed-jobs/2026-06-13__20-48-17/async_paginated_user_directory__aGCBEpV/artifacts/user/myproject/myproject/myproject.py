import reflex as rx
import math
from sqlmodel import select, func

class User(rx.Model, table=True):
    username: str
    email: str

async def fetch_users_query(session, page: int, page_size: int, search_query: str):
    q = select(User)
    if search_query:
        q = q.where(func.lower(User.username).contains(search_query.lower()))
    
    count_q = select(func.count()).select_from(q.subquery())
    total_users = (await session.exec(count_q)).one()
    
    q = q.offset((page - 1) * page_size).limit(page_size).order_by(User.id)
    items = (await session.exec(q)).all()
    
    return items, total_users

class State(rx.State):
    page: int = 1
    page_size: int = 10
    search_query: str = ""
    users: list[User] = []
    total_users: int = 0
    total_pages: int = 0

    @rx.event(background=True)
    async def fetch_page(self):
        async with self:
            current_page = self.page
            current_page_size = self.page_size
            current_search = self.search_query

        async with rx.asession() as session:
            items, total_users = await fetch_users_query(
                session, current_page, current_page_size, current_search
            )

        async with self:
            self.users = list(items)
            self.total_users = total_users
            self.total_pages = math.ceil(total_users / current_page_size) if total_users > 0 else 0

    def set_search_query(self, query: str):
        self.search_query = query
        self.page = 1
        return State.fetch_page

    def next_page(self):
        if self.page < self.total_pages:
            self.page += 1
            return State.fetch_page

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            return State.fetch_page

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("User Directory"),
            rx.input(
                placeholder="Search users...",
                value=State.search_query,
                on_change=State.set_search_query,
            ),
            rx.text(f"Page {State.page} of {State.total_pages}"),
            rx.hstack(
                rx.button(
                    "Previous", 
                    on_click=State.prev_page,
                    disabled=State.page <= 1
                ),
                rx.button(
                    "Next", 
                    on_click=State.next_page,
                    disabled=State.page >= State.total_pages
                ),
            ),
            rx.foreach(
                State.users,
                lambda user: rx.box(
                    rx.text(user.username, font_weight="bold"),
                    rx.text(user.email, color="gray"),
                    border="1px solid #ccc",
                    padding="10px",
                    margin_bottom="10px",
                    border_radius="5px",
                    width="100%"
                )
            ),
            width="100%",
            max_width="600px",
            margin="0 auto",
            padding="20px",
        ),
        on_mount=State.fetch_page
    )

app = rx.App()
app.add_page(index)
