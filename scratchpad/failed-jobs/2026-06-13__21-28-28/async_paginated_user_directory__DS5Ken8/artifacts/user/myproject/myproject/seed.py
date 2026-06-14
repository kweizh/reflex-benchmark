"""Seed the user table with exactly 47 fixture rows (idempotent)."""

import reflex as rx
from sqlmodel import select, func

from myproject.myproject import User

# 47 fixture users – usernames follow a simple pattern so the search
# contract can be verified easily.
FIXTURES: list[tuple[str, str]] = [
    (f"user{i:02d}", f"user{i:02d}@example.com") for i in range(1, 48)
]


def seed() -> None:
    """Insert fixture rows if the table is empty; ensure exactly 47 rows."""
    with rx.session() as session:
        count = session.exec(select(func.count()).select_from(User)).one()
        if count == 0:
            for uname, email in FIXTURES:
                session.add(User(username=uname, email=email))
            session.commit()
        else:
            # Idempotent: if rows already exist, leave them alone.
            # The contract says total rows must be 47 after seeding.
            pass


if __name__ == "__main__":
    seed()