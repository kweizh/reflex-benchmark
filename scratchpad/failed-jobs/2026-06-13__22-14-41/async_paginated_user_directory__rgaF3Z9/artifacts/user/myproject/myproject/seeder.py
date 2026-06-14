"""Seeder: ensures the database contains exactly the 47 fixture users.

Idempotent — re-running does not duplicate rows.
"""

import reflex as rx
from sqlmodel import select

from .models import User
from .seed_data import FIXTURE_USERS


async def seed():
    """Seed the database with fixture users if not already present."""
    async with rx.asession() as session:
        # Check current count
        count_result = await session.execute(select(User))
        existing = count_result.scalars().all()

        if len(existing) >= len(FIXTURE_USERS):
            # Already seeded — idempotent
            return

        # Insert all fixture users
        for u_data in FIXTURE_USERS:
            user = User(username=u_data["username"], email=u_data["email"])
            session.add(user)

        await session.commit()
