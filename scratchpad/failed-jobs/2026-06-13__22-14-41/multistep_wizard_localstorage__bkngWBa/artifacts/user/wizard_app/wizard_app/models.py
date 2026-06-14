"""Database models for the wizard application."""

import reflex as rx
from sqlmodel import Field


class Submission(rx.Model, table=True):
    """Stores completed wizard submissions."""

    __tablename__ = "submission"

    full_name: str = Field(max_length=100)
    email: str = Field(max_length=254)
    street: str = Field(max_length=200)
    city: str = Field(max_length=100)
    postal_code: str = Field(max_length=5)
    newsletter: bool = Field(default=False)
    theme: str = Field(max_length=10)
    language: str = Field(max_length=2)
    created_at: str = Field(max_length=30)
