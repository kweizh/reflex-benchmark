import sys
import os
import json
import argparse
from sqlmodel import Session, create_engine, select, func, delete, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional

# Add current dir to path to import models
sys.path.append(os.getcwd())
from myproject.models import Note, Tag, NoteTagLink

DB_URL = "sqlite:///reflex.db"
engine = create_engine(DB_URL)

def get_counts():
    with Session(engine) as session:
        notes = session.exec(select(func.count()).select_from(Note)).one()
        tags = session.exec(select(func.count()).select_from(Tag)).one()
        links = session.exec(select(func.count()).select_from(NoteTagLink)).one()
        print(json.dumps({"notes": notes, "tags": tags, "links": links}))

def ensure_tag(name: str):
    with Session(engine) as session:
        tag = session.exec(select(Tag).where(Tag.name == name)).first()
        created = False
        if not tag:
            tag = Tag(name=name)
            session.add(tag)
            session.commit()
            session.refresh(tag)
            created = True
        print(json.dumps({"id": tag.id, "name": tag.name, "created": created}))

def create_note(content: str, tags_str: Optional[str]):
    tag_names = []
    if tags_str:
        tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
    
    with Session(engine) as session:
        tags = []
        for name in tag_names:
            tag = session.exec(select(Tag).where(Tag.name == name)).first()
            if not tag:
                tag = Tag(name=name)
                session.add(tag)
                session.commit()
                session.refresh(tag)
            tags.append(tag)
        
        note = Note(content=content, tags=tags)
        session.add(note)
        session.commit()
        session.refresh(note)
        
        sorted_tags = sorted([t.name for t in note.tags])
        print(json.dumps({"id": note.id, "content": note.content, "tags": sorted_tags}))

def list_notes(filter_str: Optional[str]):
    filter_tags = []
    if filter_str:
        filter_tags = [t.strip() for t in filter_str.split(",") if t.strip()]
    
    with Session(engine) as session:
        if not filter_tags:
            statement = select(Note).options(selectinload(Note.tags)).order_by(Note.id)
            notes = session.exec(statement).all()
        else:
            # notes that have at least one tag in filter_tags
            statement = select(Note).join(NoteTagLink).join(Tag).where(Tag.name.in_(filter_tags)).options(selectinload(Note.tags)).distinct().order_by(Note.id)
            notes = session.exec(statement).all()
        
        result = []
        for n in notes:
            result.append({
                "id": n.id,
                "content": n.content,
                "tags": sorted([t.name for t in n.tags])
            })
        print(json.dumps({"notes": result}))

def set_tags(note_id: int, tags_str: str):
    tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
    with Session(engine) as session:
        note = session.get(Note, note_id)
        if not note:
            sys.exit(1)
        
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
        session.refresh(note)
        
        print(json.dumps({"id": note.id, "tags": sorted([t.name for t in note.tags])}))

def update_note(note_id: int, content: str):
    with Session(engine) as session:
        note = session.get(Note, note_id)
        if not note:
            sys.exit(1)
        note.content = content
        session.add(note)
        session.commit()
        session.refresh(note)
        print(json.dumps({"id": note.id, "content": note.content}))

def delete_note(note_id: int):
    with Session(engine) as session:
        note = session.get(Note, note_id)
        if not note:
            sys.exit(1)
        session.delete(note)
        session.commit()
        print(json.dumps({"id": note_id, "deleted": True}))

def all_tags():
    with Session(engine) as session:
        statement = select(Tag.name).join(NoteTagLink).distinct().order_by(Tag.name)
        tags = session.exec(statement).all()
        print(json.dumps({"all_tags": list(tags)}))

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("counts")
    
    ensure_tag_parser = subparsers.add_parser("ensure-tag")
    ensure_tag_parser.add_argument("--name", required=True)
    
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--content", required=True)
    create_parser.add_argument("--tags")
    
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--filter")
    
    set_tags_parser = subparsers.add_parser("set-tags")
    set_tags_parser.add_argument("--id", type=int, required=True)
    set_tags_parser.add_argument("--tags", required=True)
    
    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--id", type=int, required=True)
    update_parser.add_argument("--content", required=True)
    
    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("--id", type=int, required=True)
    
    subparsers.add_parser("all-tags")

    args = parser.parse_args()

    if args.command == "counts":
        get_counts()
    elif args.command == "ensure-tag":
        ensure_tag(args.name)
    elif args.command == "create":
        create_note(args.content, args.tags)
    elif args.command == "list":
        list_notes(args.filter)
    elif args.command == "set-tags":
        set_tags(args.id, args.tags)
    elif args.command == "update":
        update_note(args.id, args.content)
    elif args.command == "delete":
        delete_note(args.id)
    elif args.command == "all-tags":
        all_tags()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
