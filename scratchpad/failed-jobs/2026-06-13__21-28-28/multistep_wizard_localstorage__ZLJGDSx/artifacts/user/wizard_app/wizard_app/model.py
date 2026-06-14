"""Database model for the submission table."""

import sqlmodel

import reflex as rx


class Submission(rx.Model, table=True):
    """Model for storing form submissions."""

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    full_name: str = sqlmodel.Field(default="")
    email: str = sqlmodel.Field(default="")
    street: str = sqlmodel.Field(default="")
    city: str = sqlmodel.Field(default="")
    postal_code: str = sqlmodel.Field(default="")
    newsletter: bool = sqlmodel.Field(default=False)
    theme: str = sqlmodel.Field(default="")
    language: str = sqlmodel.Field(default="")
    created_at: str = sqlmodel.Field(default="")