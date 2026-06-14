import asyncio
import reflex as rx
from myproject.myproject import User
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

async def seed():
    engine = create_async_engine("sqlite+aiosqlite:///reflex.db")
    async with AsyncSession(engine) as session:
        # Check if we already have 47 users
        statement = select(func.count()).select_from(User)
        count = (await session.exec(statement)).one()
        
        if count == 47:
            print("Database already seeded with 47 users.")
            return

        # Clear existing users if any to ensure exactly 47
        if count > 0:
            print(f"Found {count} users, resetting to 47...")
            existing_users = (await session.exec(select(User))).all()
            for u in existing_users:
                await session.delete(u)
            await session.commit()

        print("Seeding 47 users...")
        for i in range(1, 48):
            user = User(username=f"user{i:02d}", email=f"user{i:02d}@example.com")
            session.add(user)
        await session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed())
