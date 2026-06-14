import reflex as rx
from .models import Note, Tag, NoteTagLink
from typing import List, Set
from sqlmodel import select, delete
from sqlalchemy.orm import selectinload
import sqlalchemy

class State(rx.State):
    notes: List[Note] = []
    selected_tags: List[str] = []
    
    # Form fields
    new_content: str = ""
    new_tags: str = ""
    
    editing_id: int = -1
    edit_content: str = ""
    edit_tags: str = ""

    # Setters (if not auto-generated)
    def set_new_content(self, v): self.new_content = v
    def set_new_tags(self, v): self.new_tags = v
    def set_edit_content(self, v): self.edit_content = v
    def set_edit_tags(self, v): self.edit_tags = v

    def load_notes(self):
        with rx.session() as session:
            statement = select(Note).options(selectinload(Note.tags)).order_by(Note.id)
            self.notes = session.exec(statement).all()

    @rx.var(cache=True)
    def all_tags(self) -> List[str]:
        with rx.session() as session:
            statement = select(Tag.name).join(NoteTagLink).distinct().order_by(Tag.name)
            return [str(t) for t in session.exec(statement).all()]

    @rx.var
    def visible_note_ids(self) -> List[int]:
        if not self.selected_tags:
            return [n.id for n in self.notes if n.id is not None]
        visible = []
        for note in self.notes:
            note_tags = [t.name for t in note.tags]
            if any(t in note_tags for t in self.selected_tags):
                if note.id is not None:
                    visible.append(note.id)
        return visible

    def add_note(self):
        if not self.new_content:
            return
        
        tag_names = sorted(list(set([t.strip() for t in self.new_tags.split(",") if t.strip()])))
        
        with rx.session() as session:
            tags = []
            for name in tag_names:
                tag = session.exec(select(Tag).where(Tag.name == name)).first()
                if not tag:
                    tag = Tag(name=name)
                    session.add(tag)
                    session.commit()
                    session.refresh(tag)
                tags.append(tag)
            
            new_note = Note(content=self.new_content, tags=tags)
            session.add(new_note)
            session.commit()
        
        self.new_content = ""
        self.new_tags = ""
        self.load_notes()

    def delete_note(self, note_id: int):
        with rx.session() as session:
            note = session.get(Note, note_id)
            if note:
                session.delete(note)
                session.commit()
        self.load_notes()

    def set_editing(self, note: Note):
        self.editing_id = note.id
        self.edit_content = note.content
        with rx.session() as session:
            n = session.get(Note, note.id)
            self.edit_tags = ",".join(sorted([t.name for t in n.tags]))

    def cancel_edit(self):
        self.editing_id = -1
        self.edit_content = ""
        self.edit_tags = ""

    def save_edit(self):
        if self.editing_id == -1:
            return
        
        tag_names = sorted(list(set([t.strip() for t in self.edit_tags.split(",") if t.strip()])))
        
        with rx.session() as session:
            note = session.get(Note, self.editing_id)
            if note:
                note.content = self.edit_content
                
                # Update tags
                new_tags = []
                for name in tag_names:
                    tag = session.exec(select(Tag).where(Tag.name == name)).first()
                    if not tag:
                        tag = Tag(name=name)
                        session.add(tag)
                        session.commit()
                        session.refresh(tag)
                    new_tags.append(tag)
                
                note.tags = new_tags
                session.add(note)
                session.commit()
        
        self.editing_id = -1
        self.load_notes()

    def toggle_tag_filter(self, tag_name: str):
        if tag_name in self.selected_tags:
            self.selected_tags.remove(tag_name)
        else:
            self.selected_tags.append(tag_name)

    def on_load(self):
        self.load_notes()

def note_row(note: Note):
    return rx.cond(
        State.visible_note_ids.contains(note.id),
        rx.vstack(
            rx.hstack(
                rx.text(note.content, font_weight="bold"),
                rx.spacer(),
                rx.button("Edit", on_click=lambda: State.set_editing(note)),
                rx.button("Delete", on_click=lambda: State.delete_note(note.id), color_scheme="red"),
            ),
            rx.hstack(
                rx.foreach(note.tags, lambda t: rx.badge(t.name, color_scheme="blue"))
            ),
            border_bottom="1px solid #ccc",
            padding="1em",
            width="100%",
            align_items="start",
        )
    )

def index() -> rx.Component:
    return rx.container(
        rx.heading("Notes & Tags", size="9", margin_bottom="0.5em"),
        
        # Filter UI
        rx.vstack(
            rx.text("Filter by Tags:", font_weight="bold"),
            rx.hstack(
                rx.foreach(State.all_tags, lambda tag: rx.button(
                    tag, 
                    on_click=lambda: State.toggle_tag_filter(tag),
                    color_scheme=rx.cond(State.selected_tags.contains(tag), "green", "gray"),
                    variant="soft",
                )),
                wrap="wrap",
                spacing="2",
            ),
            padding="1em",
            background="#f0f0f0",
            border_radius="0.5em",
            margin_bottom="1em",
            align_items="start",
        ),
        
        # Add Note UI
        rx.vstack(
            rx.heading("Add New Note", size="5"),
            rx.input(placeholder="Content", value=State.new_content, on_change=State.set_new_content, width="100%"),
            rx.input(placeholder="Tags (comma separated)", value=State.new_tags, on_change=State.set_new_tags, width="100%"),
            rx.button("Add Note", on_click=State.add_note, width="100%"),
            padding="1em",
            border="1px solid #eee",
            border_radius="0.5em",
            margin_bottom="1em",
            align_items="start",
        ),
        
        # Edit Note UI
        rx.cond(
            State.editing_id != -1,
            rx.vstack(
                rx.heading("Edit Note", size="5"),
                rx.input(value=State.edit_content, on_change=State.set_edit_content, width="100%"),
                rx.input(value=State.edit_tags, on_change=State.set_edit_tags, width="100%"),
                rx.hstack(
                    rx.button("Save", on_click=State.save_edit, color_scheme="green"),
                    rx.button("Cancel", on_click=State.cancel_edit, variant="ghost"),
                ),
                padding="1em",
                background="#fffbeb",
                border="1px solid #fde68a",
                border_radius="0.5em",
                margin_bottom="1em",
                width="100%",
                align_items="start",
            )
        ),

        # Notes List
        rx.vstack(
            rx.heading("Notes", size="5"),
            rx.foreach(State.notes, note_row),
            width="100%",
            align_items="start",
        ),
        on_mount=State.on_load,
        padding="2em",
    )

app = rx.App()
app.add_page(index)
