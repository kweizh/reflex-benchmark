import reflex as rx
import sqlmodel

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
            
            offset = (page - 1) * page_size
            stmt = User.select().offset(offset).limit(page_size)
            result = await session.execute(stmt)
            fetched_users = [row[0] for row in result.all()]
            
            async with self:
                self.users = fetched_users

    @rx.event(background=True)
    async def on_load(self):
        async with rx.asession() as session:
            stmt = User.select()
            result = await session.execute(stmt)
            all_users = result.all()
            if len(all_users) == 0:
                # Seed at least 50 distinct users when the table is empty
                for i in range(1, 56):
                    user = User(username=f"user_{i}", email=f"user_{i}@example.com")
                    session.add(user)
                await session.commit()
        
        # Trigger fetch_page to load the first page
        yield State.fetch_page

    @rx.event
    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            return State.fetch_page

    @rx.event
    def next_page(self):
        self.page += 1
        return State.fetch_page

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("User Directory", size="8"),
            
            # The table populated from users showing username and email for the current page
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
                    )
                ),
                width="100%",
                variant="surface",
            ),
            
            # Pagination controls
            rx.hstack(
                rx.button("Prev", on_click=State.prev_page, disabled=State.page <= 1),
                rx.text("Page ", State.page),
                rx.button("Next", on_click=State.next_page),
                rx.text("Page Size: ", State.page_size),
                spacing="4",
                align="center",
            ),
            spacing="5",
            width="100%",
            padding_y="5",
        )
    )

app = rx.App()
# Wire the index page so it triggers fetch_page on page load
app.add_page(index, on_load=State.on_load)
