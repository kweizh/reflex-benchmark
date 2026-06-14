import sys
import json
import argparse
from sqlmodel import Session, select, create_engine, func
from sqlalchemy.orm import selectinload

# Import models from myproject
from myproject.myproject import Note, Tag, NoteTagLink

# Reflex uses sqlite:///reflex.db by default
engine = create_engine("sqlite:///reflex.db")

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    counts_parser = subparsers.add_parser("counts")
    
    ensure_tag_parser = subparsers.add_parser("ensure-tag")
    ensure_tag_parser.add_argument("--name", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--content", required=True)
    create_parser.add_argument("--tags", default="")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--filter", default="")

    set_tags_parser = subparsers.add_parser("set-tags")
    set_tags_parser.add_argument("--id", type=int, required=True)
    set_tags_parser.add_argument("--tags", default="")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--id", type=int, required=True)
    update_parser.add_argument("--content", required=True)

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("--id", type=int, required=True)

    all_tags_parser = subparsers.add_parser("all-tags")

    args = parser.parse_args()

    with Session(engine) as session:
        if args.command == "counts":
            notes_count = session.scalar(select(func.count()).select_from(Note))
            tags_count = session.scalar(select(func.count()).select_from(Tag))
            links_count = session.scalar(select(func.count()).select_from(NoteTagLink))
            print(json.dumps({"notes": notes_count, "tags": tags_count, "links": links_count}))
        
        elif args.command == "ensure-tag":
            tag = session.exec(select(Tag).where(Tag.name == args.name)).first()
            created = False
            if not tag:
                tag = Tag(name=args.name)
                session.add(tag)
                session.commit()
                session.refresh(tag)
                created = True
            print(json.dumps({"id": tag.id, "name": tag.name, "created": created}))

        elif args.command == "create":
            note = Note(content=args.content)
            tag_names = [t.strip() for t in args.tags.split(",")] if args.tags else []
            tag_names = [t for t in tag_names if t]
            for name in tag_names:
                tag = session.exec(select(Tag).where(Tag.name == name)).first()
                if not tag:
                    tag = Tag(name=name)
                    session.add(tag)
                note.tags.append(tag)
            session.add(note)
            session.commit()
            session.refresh(note)
            sorted_tags = sorted([t.name for t in note.tags])
            print(json.dumps({"id": note.id, "content": note.content, "tags": sorted_tags}))

        elif args.command == "list":
            filters = [t.strip() for t in args.filter.split(",")] if args.filter else []
            filters = [t for t in filters if t]
            
            statement = select(Note).options(selectinload(Note.tags)).order_by(Note.id)
            notes = session.exec(statement).all()
            
            result = []
            for note in notes:
                note_tags = sorted([t.name for t in note.tags])
                if not filters or any(f in note_tags for f in filters):
                    result.append({"id": note.id, "content": note.content, "tags": note_tags})
            print(json.dumps({"notes": result}))

        elif args.command == "set-tags":
            note = session.exec(select(Note).options(selectinload(Note.tags)).where(Note.id == args.id)).first()
            if not note:
                sys.exit(1)
            note.tags.clear()
            tag_names = [t.strip() for t in args.tags.split(",")] if args.tags else []
            tag_names = [t for t in tag_names if t]
            for name in tag_names:
                tag = session.exec(select(Tag).where(Tag.name == name)).first()
                if not tag:
                    tag = Tag(name=name)
                    session.add(tag)
                note.tags.append(tag)
            session.add(note)
            session.commit()
            sorted_tags = sorted([t.name for t in note.tags])
            print(json.dumps({"id": note.id, "tags": sorted_tags}))

        elif args.command == "update":
            note = session.exec(select(Note).where(Note.id == args.id)).first()
            if not note:
                sys.exit(1)
            note.content = args.content
            session.add(note)
            session.commit()
            print(json.dumps({"id": note.id, "content": note.content}))

        elif args.command == "delete":
            note = session.exec(select(Note).where(Note.id == args.id)).first()
            if not note:
                sys.exit(1)
            session.delete(note)
            session.commit()
            print(json.dumps({"id": args.id, "deleted": True}))

        elif args.command == "all-tags":
            # Tag names attached to at least one note
            statement = select(Tag).join(NoteTagLink).distinct()
            tags = session.exec(statement).all()
            sorted_tags = sorted([t.name for t in tags])
            print(json.dumps({"all_tags": sorted_tags}))

if __name__ == "__main__":
    main()
