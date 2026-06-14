import asyncio
import json
import argparse
import reflex as rx
from myproject.myproject import User, get_query_results
import math
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

async def probe(page: int, search: str = ""):
    page_size = 10
    count_query, paginated_query = get_query_results(search, page, page_size)
    
    engine = create_async_engine("sqlite+aiosqlite:///reflex.db")
    async with AsyncSession(engine) as session:
        total_users = (await session.exec(count_query)).one()
        users = (await session.exec(paginated_query)).all()
        
    total_pages = math.ceil(total_users / page_size) if total_users > 0 else 0
    
    result = {
        "page": page,
        "page_size": page_size,
        "total_users": total_users,
        "total_pages": total_pages,
        "items": [
            {"id": u.id, "username": u.username, "email": u.email}
            for u in users
        ]
    }
    print(json.dumps(result))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--search", type=str, default="")
    args = parser.parse_args()
    
    asyncio.run(probe(args.page, args.search))
