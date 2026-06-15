"""CRUD User Management App with Reflex."""

import reflex as rx
import sqlmodel

from rxconfig import config


class User(rx.Model, table=True):
    """User model stored in SQLite."""

    username: str
    email: str
    is_active: bool = True


class State(rx.State):
    """The app state."""

    users: list[User] = []
    new_username: str = ""
    new_email: str = ""

    def set_new_username(self, value: str):
        """Set the new username field."""
        self.new_username = value

    def set_new_email(self, value: str):
        """Set the new email field."""
        self.new_email = value

    def load_users(self):
        """Load all users from the database."""
        with rx.session() as session:
            self.users = session.exec(sqlmodel.select(User)).all()

    def create_user(self):
        """Create a new user."""
        if not self.new_username.strip() or not self.new_email.strip():
            return
        with rx.session() as session:
            user = User(
                username=self.new_username.strip(),
                email=self.new_email.strip(),
                is_active=True,
            )
            session.add(user)
            session.commit()
        self.new_username = ""
        self.new_email = ""
        return State.load_users

    def delete_user(self, user_id: int):
        """Delete a user by id."""
        with rx.session() as session:
            user = session.get(User, user_id)
            if user:
                session.delete(user)
                session.commit()
        return State.load_users

    def toggle_active(self, user_id: int):
        """Toggle the is_active flag of a user."""
        with rx.session() as session:
            user = session.get(User, user_id)
            if user:
                user.is_active = not user.is_active
                session.add(user)
                session.commit()
        return State.load_users


def user_row(user: User) -> rx.Component:
    """Render a single user table row."""
    return rx.table.row(
        rx.table.cell(user.username),
        rx.table.cell(user.email),
        rx.table.cell(
            rx.cond(
                user.is_active,
                rx.badge("Active", color_scheme="green"),
                rx.badge("Inactive", color_scheme="red"),
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    "Delete",
                    color_scheme="red",
                    size="1",
                    on_click=State.delete_user(user.id),
                ),
                rx.button(
                    "Toggle",
                    color_scheme="blue",
                    size="1",
                    on_click=State.toggle_active(user.id),
                ),
                spacing="2",
            )
        ),
    )


def index() -> rx.Component:
    """The main page."""
    return rx.container(
        rx.vstack(
            rx.heading("User Management", size="8"),
            # Create user form
            rx.card(
                rx.vstack(
                    rx.heading("Create New User", size="5"),
                    rx.input(
                        placeholder="Username",
                        value=State.new_username,
                        on_change=State.set_new_username,
                        width="100%",
                    ),
                    rx.input(
                        placeholder="Email",
                        value=State.new_email,
                        on_change=State.set_new_email,
                        width="100%",
                    ),
                    rx.button(
                        "Create",
                        on_click=State.create_user,
                        color_scheme="green",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            # Users table
            rx.card(
                rx.vstack(
                    rx.heading("Users", size="5"),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Username"),
                                rx.table.column_header_cell("Email"),
                                rx.table.column_header_cell("Status"),
                                rx.table.column_header_cell("Actions"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(State.users, user_row)
                        ),
                        width="100%",
                    ),
                    width="100%",
                ),
                width="100%",
            ),
            spacing="5",
            width="100%",
            padding="4",
        ),
        on_mount=State.load_users,
    )


app = rx.App()
app.add_page(index)
