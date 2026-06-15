"""User Management CRUD Application with Reflex"""

import reflex as rx
from sqlmodel import select


class User(rx.Model, table=True):
    username: str
    email: str
    is_active: bool = True


class State(rx.State):
    users: list[User] = []

    def load_users(self):
        with rx.session() as session:
            self.users = session.exec(select(User)).all()

    def create_user(self, form_data: dict):
        username = form_data.get("username")
        email = form_data.get("email")
        if not username or not email:
            return
        new_user = User(username=username, email=email)
        with rx.session() as session:
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


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("User Management CRUD", size="6"),
            rx.divider(),
            rx.form(
                rx.vstack(
                    rx.heading("Add New User", size="4"),
                    rx.input(placeholder="Username", name="username", required=True),
                    rx.input(placeholder="Email", type="email", name="email", required=True),
                    rx.button("Create", type="submit"),
                    spacing="3",
                    align_items="stretch",
                ),
                on_submit=State.create_user,
                reset_on_submit=True,
                width="100%",
                max_width="400px",
            ),
            rx.divider(),
            rx.vstack(
                rx.heading("Users List", size="4"),
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
                        rx.foreach(
                            State.users,
                            lambda user: rx.table.row(
                                rx.table.cell(user.username),
                                rx.table.cell(user.email),
                                rx.table.cell(rx.cond(user.is_active, "Yes", "No")),
                                rx.table.cell(
                                    rx.hstack(
                                        rx.button(
                                            "Toggle",
                                            on_click=State.toggle_active(user.id),
                                        ),
                                        rx.button(
                                            "Delete",
                                            on_click=State.delete_user(user.id),
                                        ),
                                        spacing="2",
                                    )
                                ),
                            )
                        )
                    ),
                    width="100%",
                ),
                width="100%",
                spacing="3",
            ),
            spacing="5",
            align_items="stretch",
            padding="4",
        )
    )


app = rx.App()
app.add_page(index, on_load=State.load_users)
