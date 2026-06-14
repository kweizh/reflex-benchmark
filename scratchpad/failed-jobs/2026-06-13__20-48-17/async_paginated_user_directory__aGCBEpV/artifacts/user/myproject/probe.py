import argparse
import asyncio
import json
import math
import sys
import os

# Suppress stdout and stderr during imports
old_stdout = sys.stdout
old_stderr = sys.stderr
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

import reflex as rx
from myproject.myproject import User, fetch_users_query

# Restore stdout and stderr
sys.stdout.close()
sys.stderr.close()
sys.stdout = old_stdout
sys.stderr = old_stderr

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--search", type=str, default="")
    args = parser.parse_args()

    page = args.page
    search_query = args.search
    page_size = 10

    async with rx.asession() as session:
        items, total_users = await fetch_users_query(
            session, page, page_size, search_query
        )

    total_pages = math.ceil(total_users / page_size) if total_users > 0 else 0
    
    if page > total_pages:
        items = []

    result = {
        "page": page,
        "page_size": page_size,
        "total_users": total_users,
        "total_pages": total_pages,
        "items": [
            {"id": item.id, "username": item.username, "email": item.email}
            for item in items
        ]
    }
    print(json.dumps(result))

if __name__ == "__main__":
    asyncio.run(main())
