import asyncio
import reflex as rx
from sqlmodel import select
from myproject.myproject import User

async def seed():
    async with rx.asession() as session:
        # Check current count
        count = (await session.exec(select(User))).all()
        if len(count) == 47:
            print("Already seeded.")
            return

        # Delete existing if not 47 just to be safe
        for u in count:
            await session.delete(u)
        await session.commit()

        # Insert 47 users
        for i in range(1, 48):
            user = User(username=f"User{i}", email=f"user{i}@example.com")
            session.add(user)
        
        await session.commit()
        print("Seeded 47 users.")

if __name__ == "__main__":
    asyncio.run(seed())
