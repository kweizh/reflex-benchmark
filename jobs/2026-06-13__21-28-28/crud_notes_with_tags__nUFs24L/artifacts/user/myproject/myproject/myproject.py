"""Notes & Tags Reflex app with many-to-many filtering."""

import reflex as rx
import sqlmodel
from typing import List, Optional


# ── Link table ──────────────────────────────────────────────────────────────
class NoteTagLink(rx.Model, table=True):
    """Link table joining Note and Tag (many-to-many)."""

    note_id: Optional[int] = sqlmodel.Field(
        default=None, foreign_key="note.id", primary_key=True
    )
    tag_id: Optional[int] = sqlmodel.Field(
        default=None, foreign_key="tag.id", primary_key=True
    )


# ── Tag model ────────────────────────────────────────────────────────────────
class Tag(rx.Model, table=True):
    """A tag that can be attached to notes."""

    name: str = sqlmodel.Field(unique=True)
    notes: List[Note] = sqlmodel.Relationship(
        back_populates="tags", link_model=NoteTagLink
    )


# ── Note model ──────────────────────────────────────────────────────────────
class Note(rx.Model, table=True):
    """A note that can have multiple tags."""

    content: str = ""
    tags: List[Tag] = sqlmodel.Relationship(
        back_populates="notes", link_model=NoteTagLink
    )


# ── State ────────────────────────────────────────────────────────────────────
class State(rx.State):
    """The app state."""

    notes: List[Note] = []
    selected_tags: List[str] = []

    # Form fields
    new_content: str = ""
    new_tags_input: str = ""
    edit_note_id: Optional[int] = None
    edit_content: str = ""
    edit_tags_input: str = ""

    def load_notes(self) -> None:
        """Load all notes from the database (sorted by id)."""
        with rx.model.session() as session:
            notes = session.exec(
                sqlmodel.select(Note).order_by(Note.id)
            ).all()
            # Force-load the tags relationship for each note
            for n in notes:
                _ = n.tags
            self.notes = notes

    @rx.var(cache=True)
    def all_tags(self) -> List[str]:
        """Return sorted union of tag names attached to at least one note."""
        tag_names: set[str] = set()
        for note in self.notes:
            for tag in note.tags:
                tag_names.add(tag.name)
        return sorted(tag_names)

    def toggle_tag(self, tag_name: str) -> None:
        """Toggle a tag in/out of selected_tags."""
        if tag_name in self.selected_tags:
            self.selected_tags = [
                t for t in self.selected_tags if t != tag_name
            ]
        else:
            self.selected_tags = self.selected_tags + [tag_name]

    def set_new_content(self, value: str) -> None:
        self.new_content = value

    def set_new_tags_input(self, value: str) -> None:
        self.new_tags_input = value

    def create_note(self) -> None:
        """Create a new note with content and tags."""
        with rx.model.session() as session:
            note = Note(content=self.new_content)
            session.add(note)
            session.commit()
            session.refresh(note)

            tag_names = [
                t.strip() for t in self.new_tags_input.split(",") if t.strip()
            ]
            for name in tag_names:
                tag = session.exec(
                    sqlmodel.select(Tag).where(Tag.name == name)
                ).first()
                if tag is None:
                    tag = Tag(name=name)
                    session.add(tag)
                    session.commit()
                    session.refresh(tag)
                link = NoteTagLink(note_id=note.id, tag_id=tag.id)
                session.add(link)
            session.commit()

            self.new_content = ""
            self.new_tags_input = ""
            self.load_notes()

    def start_edit(self, note_id: int) -> None:
        """Begin editing a note."""
        with rx.model.session() as session:
            note = session.get(Note, note_id)
            if note is None:
                return
            self.edit_note_id = note_id
            self.edit_content = note.content
            self.edit_tags_input = ", ".join(
                sorted(t.name for t in note.tags)
            )

    def set_edit_content(self, value: str) -> None:
        self.edit_content = value

    def set_edit_tags_input(self, value: str) -> None:
        self.edit_tags_input = value

    def save_edit(self) -> None:
        """Save edits to a note."""
        if self.edit_note_id is None:
            return
        with rx.model.session() as session:
            note = session.get(Note, self.edit_note_id)
            if note is None:
                return
            note.content = self.edit_content
            session.add(note)

            # Remove existing links
            old_links = session.exec(
                sqlmodel.select(NoteTagLink).where(
                    NoteTagLink.note_id == note.id
                )
            ).all()
            for link in old_links:
                session.delete(link)

            # Add new links
            tag_names = [
                t.strip()
                for t in self.edit_tags_input.split(",")
                if t.strip()
            ]
            for name in tag_names:
                tag = session.exec(
                    sqlmodel.select(Tag).where(Tag.name == name)
                ).first()
                if tag is None:
                    tag = Tag(name=name)
                    session.add(tag)
                    session.commit()
                    session.refresh(tag)
                link = NoteTagLink(note_id=note.id, tag_id=tag.id)
                session.add(link)

            session.commit()

        self.edit_note_id = None
        self.edit_content = ""
        self.edit_tags_input = ""
        self.load_notes()

    def cancel_edit(self) -> None:
        self.edit_note_id = None
        self.edit_content = ""
        self.edit_tags_input = ""

    def delete_note(self, note_id: int) -> None:
        """Delete a note and its link rows, but NOT tag rows."""
        with rx.model.session() as session:
            note = session.get(Note, note_id)
            if note is None:
                return
            # Delete link rows
            links = session.exec(
                sqlmodel.select(NoteTagLink).where(
                    NoteTagLink.note_id == note_id
                )
            ).all()
            for link in links:
                session.delete(link)
            session.delete(note)
            session.commit()

        self.load_notes()


# ── Helper: note visible? ────────────────────────────────────────────────────
def note_is_visible(note: Note, selected_tags: List[str]) -> rx.Var:
    """Return a Var[bool] that is True when the note should be shown."""
    # If selected_tags is empty, show all notes.
    # Otherwise show if any of the note's tag names are in selected_tags.
    tag_names = [t.name for t in note.tags]
    # If no tags selected, show everything
    cond = rx.cond(
        selected_tags.length() == 0,
        True,
        # Check if any tag_name is in selected_tags
        rx.cond(
            len(tag_names) > 0,
            any(tag_name in selected_tags for tag_name in tag_names),
            False,
        ),
    )
    return cond


# ── UI ───────────────────────────────────────────────────────────────────────
def note_row(note: Note) -> rx.Component:
    """Render a single note row with conditional visibility."""
    tag_names = [t.name for t in note.tags]
    # Build a visibility condition: show if selected_tags is empty OR any tag matches
    is_visible = rx.cond(
        State.selected_tags.length() == 0,
        True,
        rx.cond(
            len(tag_names) > 0,
            any(tn in State.selected_tags for tn in tag_names),
            False,
        ),
    )
    return rx.cond(
        is_visible,
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.text(note.content, weight="bold"),
                    rx.spacer(),
                    rx.hstack(
                        rx.button(
                            "Edit",
                            size="1",
                            on_click=State.start_edit(note.id),
                        ),
                        rx.button(
                            "Delete",
                            size="1",
                            color_scheme="red",
                            on_click=State.delete_note(note.id),
                        ),
                    ),
                    width="100%",
                ),
                rx.hstack(
                    rx.badge(tn, variant="soft")
                    for tn in tag_names
                ),
                rx.cond(
                    State.edit_note_id == note.id,
                    rx.vstack(
                        rx.input(
                            value=State.edit_content,
                            on_change=State.set_edit_content,
                            placeholder="Note content",
                        ),
                        rx.input(
                            value=State.edit_tags_input,
                            on_change=State.set_edit_tags_input,
                            placeholder="Tags (comma-separated)",
                        ),
                        rx.hstack(
                            rx.button(
                                "Save",
                                on_click=State.save_edit,
                            ),
                            rx.button(
                                "Cancel",
                                variant="outline",
                                on_click=State.cancel_edit,
                            ),
                        ),
                    ),
                ),
                spacing="2",
            ),
            width="100%",
        ),
    )


def index() -> rx.Component:
    """The main page."""
    return rx.container(
        rx.vstack(
            rx.heading("Notes & Tags", size="8"),
            # ── Tag filter ──
            rx.box(
                rx.text("Filter by tags:", weight="bold"),
                rx.hstack(
                    rx.foreach(
                        State.all_tags,
                        lambda tag_name: rx.button(
                            tag_name,
                            variant=rx.cond(
                                State.selected_tags.contains(tag_name),
                                "solid",
                                "outline",
                            ),
                            on_click=State.toggle_tag(tag_name),
                            size="2",
                        ),
                    ),
                    wrap=True,
                    spacing="2",
                ),
                margin_bottom="1em",
            ),
            # ── Create note form ──
            rx.card(
                rx.vstack(
                    rx.text("New Note", weight="bold"),
                    rx.input(
                        value=State.new_content,
                        on_change=State.set_new_content,
                        placeholder="Note content",
                    ),
                    rx.input(
                        value=State.new_tags_input,
                        on_change=State.set_new_tags_input,
                        placeholder="Tags (comma-separated)",
                    ),
                    rx.button("Create Note", on_click=State.create_note),
                    spacing="2",
                ),
                width="100%",
            ),
            # ── Notes list via rx.foreach + rx.cond ──
            rx.foreach(State.notes, note_row),
            spacing="4",
            align="stretch",
        ),
        max_width="600px",
        on_mount=State.load_notes,
    )


app = rx.App()
app.add_page(index)