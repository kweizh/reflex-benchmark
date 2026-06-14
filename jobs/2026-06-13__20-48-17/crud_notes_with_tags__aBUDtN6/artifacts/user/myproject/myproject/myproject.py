import reflex as rx
from sqlmodel import Field, Relationship, select, Session
from sqlalchemy.orm import selectinload
from typing import List, Optional

class NoteTagLink(rx.Model, table=True):
    __tablename__ = "notetaglink"
    id: Optional[int] = Field(default=None, primary_key=True)
    note_id: Optional[int] = Field(default=None, foreign_key="note.id")
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.id")

class Tag(rx.Model, table=True):
    __tablename__ = "tag"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    notes: List["Note"] = Relationship(back_populates="tags", link_model=NoteTagLink)

class Note(rx.Model, table=True):
    __tablename__ = "note"
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    tags: List[Tag] = Relationship(back_populates="notes", link_model=NoteTagLink)

class State(rx.State):
    notes: List[Note] = []
    selected_tags: List[str] = []
    
    new_note_content: str = ""
    new_note_tags: str = ""
    
    edit_note_id: int = -1
    edit_note_content: str = ""
    edit_note_tags: str = ""

    def set_new_note_content(self, val: str):
        self.new_note_content = val

    def set_new_note_tags(self, val: str):
        self.new_note_tags = val

    def set_edit_note_content(self, val: str):
        self.edit_note_content = val

    def set_edit_note_tags(self, val: str):
        self.edit_note_tags = val

    def load_notes(self):
        with rx.session() as session:
            statement = select(Note).options(selectinload(Note.tags)).order_by(Note.id)
            self.notes = session.exec(statement).all()

    @rx.var(cache=True)
    def all_tags(self) -> List[str]:
        tags = set()
        for note in self.notes:
            for tag in note.tags:
                tags.add(tag.name)
        return sorted(list(tags))

    def toggle_tag(self, tag_name: str):
        if tag_name in self.selected_tags:
            self.selected_tags.remove(tag_name)
        else:
            self.selected_tags.append(tag_name)

    def add_note(self):
        with rx.session() as session:
            new_note = Note(content=self.new_note_content)
            if self.new_note_tags.strip():
                names = [n.strip() for n in self.new_note_tags.split(",") if n.strip()]
                for name in names:
                    tag = session.exec(select(Tag).where(Tag.name == name)).first()
                    if not tag:
                        tag = Tag(name=name)
                        session.add(tag)
                    new_note.tags.append(tag)
            session.add(new_note)
            session.commit()
        self.new_note_content = ""
        self.new_note_tags = ""
        self.load_notes()

    def delete_note(self, note_id: int):
        with rx.session() as session:
            note = session.exec(select(Note).where(Note.id == note_id)).first()
            if note:
                session.delete(note)
                session.commit()
        self.load_notes()

    def start_edit(self, note: Note):
        self.edit_note_id = note.id
        self.edit_note_content = note.content
        self.edit_note_tags = ",".join([t.name for t in note.tags])

    def save_edit(self):
        with rx.session() as session:
            note = session.exec(select(Note).options(selectinload(Note.tags)).where(Note.id == self.edit_note_id)).first()
            if note:
                note.content = self.edit_note_content
                note.tags.clear()
                if self.edit_note_tags.strip():
                    names = [n.strip() for n in self.edit_note_tags.split(",") if n.strip()]
                    for name in names:
                        tag = session.exec(select(Tag).where(Tag.name == name)).first()
                        if not tag:
                            tag = Tag(name=name)
                            session.add(tag)
                        note.tags.append(tag)
                session.add(note)
                session.commit()
        self.edit_note_id = -1
        self.load_notes()

    def cancel_edit(self):
        self.edit_note_id = -1

def render_tag(tag: Tag):
    return rx.badge(tag.name, margin_right="2px")

def render_note(note: Note):
    # Using JS interop for the condition:
    # selected_tags is empty OR note.tags has at least one tag whose name is in selected_tags
    cond_var = rx.Var(
        _js_expr=f"({str(State.selected_tags)}.length === 0 || {str(State.selected_tags)}.some(tag => {str(note)}.tags.map(t => t.name).includes(tag)))",
        _var_type=bool
    )
    
    return rx.cond(
        cond_var,
        rx.box(
            rx.cond(
                State.edit_note_id == note.id,
                rx.vstack(
                    rx.input(value=State.edit_note_content, on_change=State.set_edit_note_content),
                    rx.input(value=State.edit_note_tags, on_change=State.set_edit_note_tags),
                    rx.hstack(
                        rx.button("Save", on_click=State.save_edit),
                        rx.button("Cancel", on_click=State.cancel_edit)
                    )
                ),
                rx.vstack(
                    rx.text(note.content, font_weight="bold"),
                    rx.box(rx.foreach(note.tags, render_tag)),
                    rx.hstack(
                        rx.button("Edit", on_click=lambda: State.start_edit(note)),
                        rx.button("Delete", on_click=lambda: State.delete_note(note.id), color_scheme="red")
                    )
                )
            ),
            border="1px solid #ccc",
            padding="10px",
            margin_bottom="10px",
            border_radius="5px"
        ),
        rx.box()
    )

def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Notes & Tags"),
        rx.text("Selected tags: ", State.selected_tags.to_string()),
        rx.hstack(
            rx.foreach(
                State.all_tags,
                lambda tag: rx.button(
                    tag, 
                    on_click=lambda: State.toggle_tag(tag),
                    color_scheme=rx.cond(State.selected_tags.contains(tag), "blue", "gray")
                )
            )
        ),
        rx.vstack(
            rx.heading("Add Note", size="4"),
            rx.input(placeholder="Content", value=State.new_note_content, on_change=State.set_new_note_content),
            rx.input(placeholder="Tags (comma separated)", value=State.new_note_tags, on_change=State.set_new_note_tags),
            rx.button("Add Note", on_click=State.add_note)
        ),
        rx.divider(),
        rx.vstack(
            rx.foreach(
                State.notes,
                render_note
            )
        ),
        padding="20px"
    )

app = rx.App()
app.add_page(index, on_load=State.load_notes)
