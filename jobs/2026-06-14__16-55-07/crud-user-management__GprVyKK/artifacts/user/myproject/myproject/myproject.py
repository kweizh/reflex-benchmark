"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class User(rx.Model, table=True):
    """A user model stored in the database."""

    username: str
    email: str
    is_active: bool = True


class State(rx.State):
    """The app state."""

    users: list[User] = []
    username: str = ""
    email: str = ""

    def set_username(self, value: str):
        """Set the username."""
        self.username = value

    def set_email(self, value: str):
        """Set the email."""
        self.email = value

    def load_users(self):
        """Load all users from the database."""
        with rx.session() as session:
            self.users = session.exec(User.select()).all()

    def create_user(self):
        """Create a new user."""
        with rx.session() as session:
            user = User(username=self.username, email=self.email)
            session.add(user)
            session.commit()
            session.refresh(user)
        self.username = ""
        self.email = ""
        self.load_users()

    def delete_user(self, user_id: int):
        """Delete a user by id."""
        with rx.session() as session:
            user = session.get(User, user_id)
            if user:
                session.delete(user)
                session.commit()
        self.load_users()

    def toggle_active(self, user_id: int):
        """Toggle the is_active flag of a user."""
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
            rx.heading("User Management", size="7"),
            # Create user form
            rx.box(
                rx.vstack(
                    rx.heading("Create User", size="5"),
                    rx.input(
                        placeholder="Username",
                        value=State.username,
                        on_change=State.set_username,
                    ),
                    rx.input(
                        placeholder="Email",
                        value=State.email,
                        on_change=State.set_email,
                    ),
                    rx.button("Create", on_click=State.create_user),
                    spacing="3",
                ),
                padding="4",
                border_radius="md",
                border="1px solid #e2e8f0",
            ),
            # User table
            rx.box(
                rx.vstack(
                    rx.heading("Users", size="5"),
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
                                    rx.table.cell(
                                        rx.cond(user.is_active, "Yes", "No")
                                    ),
                                    rx.table.cell(
                                        rx.hstack(
                                            rx.button(
                                                "Delete",
                                                on_click=State.delete_user(
                                                    user.id
                                                ),
                                                color_scheme="red",
                                                size="1",
                                            ),
                                            rx.button(
                                                "Toggle",
                                                on_click=State.toggle_active(
                                                    user.id
                                                ),
                                                color_scheme="blue",
                                                size="1",
                                            ),
                                        )
                                    ),
                                ),
                            )
                        ),
                    ),
                    spacing="3",
                ),
                padding="4",
                border_radius="md",
                border="1px solid #e2e8f0",
            ),
            spacing="5",
            min_height="85vh",
        ),
        on_mount=State.load_users,
    )


app = rx.App()
app.add_page(index)