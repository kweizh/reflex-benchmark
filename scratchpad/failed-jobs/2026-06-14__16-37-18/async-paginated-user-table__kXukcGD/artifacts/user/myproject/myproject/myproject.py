import reflex as rx
from sqlmodel import select, func

class User(rx.Model, table=True):
    username: str
    email: str

class State(rx.State):
    page: int = 1
    page_size: int = 10
    users: list[User] = []

    @rx.event(background=True)
    async def fetch_page(self):
        async with rx.asession() as session:
            async with self:
                page = self.page
                page_size = self.page_size
            
            stmt = select(User).offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            users = result.scalars().all()
            
            async with self:
                self.users = users

    def next_page(self):
        self.page += 1
        return State.fetch_page

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
        return State.fetch_page

async def seed_db():
    async with rx.asession() as session:
        result = await session.execute(select(func.count(User.id)))
        count = result.scalar()
        if count == 0:
            for i in range(1, 60):
                session.add(User(username=f"user{i}", email=f"user{i}@example.com"))
            await session.commit()

def index() -> rx.Component:
    return rx.vstack(
        rx.heading("User Directory"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Username"),
                    rx.table.column_header_cell("Email"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    State.users,
                    lambda user: rx.table.row(
                        rx.table.cell(user.username),
                        rx.table.cell(user.email),
                    )
                )
            )
        ),
        rx.hstack(
            rx.button("Prev", on_click=State.prev_page),
            rx.text(f"Page {State.page}"),
            rx.button("Next", on_click=State.next_page),
        )
    )

app = rx.App()
app.add_page(index, on_load=[seed_db, State.fetch_page])
