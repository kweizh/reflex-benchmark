import reflex as rx
import asyncio

async def main():
    async with rx.asession() as session:
        print(type(session))

if __name__ == "__main__":
    asyncio.run(main())
