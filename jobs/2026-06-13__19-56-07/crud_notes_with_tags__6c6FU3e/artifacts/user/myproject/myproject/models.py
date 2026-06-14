import reflex as rx
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel

class NoteTagLink(SQLModel, table=True):
    note_id: Optional[int] = Field(default=None, foreign_key="note.id", primary_key=True)
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.id", primary_key=True)

class Tag(rx.Model, table=True):
    name: str = Field(unique=True, index=True)
    notes: List["Note"] = Relationship(back_populates="tags", link_model=NoteTagLink)

class Note(rx.Model, table=True):
    content: str
    tags: List[Tag] = Relationship(back_populates="notes", link_model=NoteTagLink)
