"""CRUD User Management application built with Reflex."""

import reflex as rx


class User(rx.Model, table=True):
    """A user model for the database."""

    username: str
    email: str
    is_active: bool = True


class State(rx.State):
    """The app state."""

    users: list[User] = []
    username: str = ""
    email: str = ""

    def load_users(self):
        """Load all users from the database."""
        with rx.session() as session:
            self.users = session.exec(User.select()).all()

    def create_user(self):
        """Create a new user in the database."""
        if not self.username.strip() or not self.email.strip():
            return
        with rx.session() as session:
            user = User(username=self.username, email=self.email)
            session.add(user)
            session.commit()
        self.username = ""
        self.email = ""
        self.load_users()

    def delete_user(self, user_id: int):
        """Delete a user by ID.

        Args:
            user_id: The ID of the user to delete.
        """
        with rx.session() as session:
            user = session.exec(User.select().where(User.id == user_id)).first()
            if user:
                session.delete(user)
                session.commit()
        self.load_users()

    def toggle_active(self, user_id: int):
        """Toggle the is_active flag for a user.

        Args:
            user_id: The ID of the user to toggle.
        """
        with rx.session() as session:
            user = session.exec(User.select().where(User.id == user_id)).first()
            if user:
                user.is_active = not user.is_active
                session.add(user)
                session.commit()
        self.load_users()


def index() -> rx.Component:
    """The main page of the app."""
    return rx.container(
        rx.vstack(
            rx.heading("User Management", size="8"),
            # Create user form
            rx.card(
                rx.vstack(
                    rx.heading("Create User", size="4"),
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
                width="100%",
            ),
            # Users table
            rx.card(
                rx.vstack(
                    rx.heading("Users", size="4"),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Username"),
                                rx.table.column_header_cell("Email"),
                                rx.table.column_header_cell("Active"),
                                rx.table.column_header_cell("Actions"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                State.users,
                                lambda user: rx.table.row(
                                    rx.table.cell(user.username),
                                    rx.table.cell(user.email),
                                    rx.table.cell(
                                        rx.badge(
                                            "Yes" if user.is_active else "No",
                                            color_scheme="green"
                                            if user.is_active
                                            else "red",
                                        ),
                                    ),
                                    rx.table.cell(
                                        rx.hstack(
                                            rx.button(
                                                "Toggle",
                                                size="1",
                                                on_click=lambda uid=user.id: State.toggle_active(
                                                    uid
                                                ),
                                            ),
                                            rx.button(
                                                "Delete",
                                                size="1",
                                                color_scheme="red",
                                                on_click=lambda uid=user.id: State.delete_user(
                                                    uid
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                        width="100%",
                    ),
                    spacing="3",
                ),
                width="100%",
            ),
            spacing="5",
            width="100%",
            padding="2em",
        ),
        max_width="800px",
        on_mount=State.load_users,
    )


app = rx.App()
app.add_page(index, route="/")
