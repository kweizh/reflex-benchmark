"""Database models for the Notes & Tags app."""

import reflex as rx
import sqlmodel
from typing import List, Optional


class NoteTagLink(rx.Model, table=True):
    """Link table joining Note and Tag (many-to-many)."""

    note_id: Optional[int] = sqlmodel.Field(
        default=None, foreign_key="note.id", primary_key=True
    )
    tag_id: Optional[int] = sqlmodel.Field(
        default=None, foreign_key="tag.id", primary_key=True
    )


class Tag(rx.Model, table=True):
    """A tag that can be attached to notes."""

    name: str = sqlmodel.Field(unique=True)
    notes: List["Note"] = sqlmodel.Relationship(
        back_populates="tags", link_model=NoteTagLink
    )


class Note(rx.Model, table=True):
    """A note that can have multiple tags."""

    content: str = ""
    tags: List[Tag] = sqlmodel.Relationship(
        back_populates="notes", link_model=NoteTagLink
    )