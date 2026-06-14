"""Database models for the user directory application."""

import reflex as rx


class User(rx.Model, table=True):
    """A user in the directory."""

    username: str
    email: str
