"""Shared query logic for paginated user directory search.

Used by both the Reflex background handler and the probe.py CLI tool.
"""

import math
from collections.abc import AsyncGenerator

import reflex as rx
from sqlalchemy import func, select
from sqlmodel import col

from .models import User

PAGE_SIZE = 10


async def query_users(
    page: int,
    search_query: str,
) -> dict:
    """Query users with pagination and optional case-insensitive search on username.

    Args:
        page: 1-indexed page number.
        search_query: Case-insensitive contains-match filter on username.
                      Empty string means no filter.

    Returns:
        A dict with keys: page, page_size, total_users, total_pages, items.
    """
    async with rx.asession() as session:
        # Build base query with optional filter
        base_query = select(User)
        if search_query:
            base_query = base_query.where(
                col(User.username).ilike(f"%{search_query}%")
            )

        # Count total matching users
        count_query = select(func.count()).select_from(base_query.subquery())
        total_users = (await session.execute(count_query)).scalar_one()

        # Compute total pages
        total_pages = (
            math.ceil(total_users / PAGE_SIZE) if total_users > 0 else 0
        )

        # Fetch the page of users, ordered by id ascending
        offset = (page - 1) * PAGE_SIZE
        items_query = base_query.order_by(col(User.id).asc()).offset(offset).limit(PAGE_SIZE)
        result = await session.execute(items_query)
        users = result.scalars().all()

        items = [
            {"id": u.id, "username": u.username, "email": u.email}
            for u in users
        ]

        return {
            "page": page,
            "page_size": PAGE_SIZE,
            "total_users": total_users,
            "total_pages": total_pages,
            "items": items,
        }
