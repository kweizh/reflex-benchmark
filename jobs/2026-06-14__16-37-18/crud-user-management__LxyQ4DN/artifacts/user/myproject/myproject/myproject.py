import reflex as rx

class User(rx.Model, table=True):
    username: str
    email: str
    is_active: bool = True

class State(rx.State):
    users: list[User] = []

    def load_users(self):
        with rx.session() as session:
            self.users = session.exec(User.select()).all()

    def create_user(self, form_data: dict):
        username = form_data.get("username")
        email = form_data.get("email")
        if username and email:
            with rx.session() as session:
                new_user = User(username=username, email=email)
                session.add(new_user)
                session.commit()
            self.load_users()

    def delete_user(self, user_id: int):
        with rx.session() as session:
            user = session.get(User, user_id)
            if user:
                session.delete(user)
                session.commit()
        self.load_users()

    def toggle_active(self, user_id: int):
        with rx.session() as session:
            user = session.get(User, user_id)
            if user:
                user.is_active = not user.is_active
                session.add(user)
                session.commit()
        self.load_users()

def render_user_row(user: User):
    return rx.table.row(
        rx.table.cell(user.username),
        rx.table.cell(user.email),
        rx.table.cell(rx.cond(user.is_active, "Yes", "No")),
        rx.table.cell(
            rx.hstack(
                rx.button("Delete", on_click=lambda: State.delete_user(user.id)),
                rx.button("Toggle", on_click=lambda: State.toggle_active(user.id)),
            )
        )
    )

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("User Management"),
            rx.form(
                rx.vstack(
                    rx.input(name="username", placeholder="Username", required=True),
                    rx.input(name="email", placeholder="Email", required=True),
                    rx.button("Create", type="submit"),
                ),
                on_submit=State.create_user,
                reset_on_submit=True,
            ),
            rx.divider(),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Username"),
                        rx.table.column_header_cell("Email"),
                        rx.table.column_header_cell("Active"),
                        rx.table.column_header_cell("Actions"),
                    )
                ),
                rx.table.body(
                    rx.foreach(State.users, render_user_row)
                )
            ),
            spacing="5",
        )
    )

app = rx.App()
app.add_page(index, on_load=State.load_users)
