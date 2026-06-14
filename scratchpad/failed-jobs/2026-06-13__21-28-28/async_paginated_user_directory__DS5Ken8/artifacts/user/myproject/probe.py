#!/usr/bin/env python3
"""CLI probe that exercises the same query path as the Reflex background handler.

Usage::

    cd /home/user/myproject && uv run python probe.py --page <N> [--search <S>]

Stdout is a single JSON object with the schema documented in the acceptance criteria.
"""

import argparse
import asyncio
import json
import math
import sys

# Ensure the project is importable
sys.path.insert(0, "/home/user/myproject")

import reflex as rx
from sqlmodel import select, func, col

from myproject.myproject import User, query_users, PAGE_SIZE


async def probe(page: int, search: str | None) -> dict:
    """Run the paginated query and return a result dict."""
    search_query = search or ""
    items, total_users = await query_users(
        page=page,
        page_size=PAGE_SIZE,
        search_query=search_query,
    )
    total_pages = math.ceil(total_users / PAGE_SIZE) if total_users > 0 else 0
    return {
        "page": page,
        "page_size": PAGE_SIZE,
        "total_users": total_users,
        "total_pages": total_pages,
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the user directory")
    parser.add_argument("--page", type=int, required=True, help="1-indexed page number")
    parser.add_argument("--search", type=str, default=None, help="case-insensitive contains filter on username")
    args = parser.parse_args()

    result = asyncio.run(probe(args.page, args.search))
    print(json.dumps(result))


if __name__ == "__main__":
    main()