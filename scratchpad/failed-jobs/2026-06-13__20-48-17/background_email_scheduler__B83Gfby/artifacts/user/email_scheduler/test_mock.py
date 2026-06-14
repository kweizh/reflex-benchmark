import reflex as rx
import asyncio

class State(rx.State):
    val: int = 0
    @rx.event(background=True)
    async def loop(self):
        async with self:
            self.val += 1
            print("Loop ran, val:", self.val)

class MockState:
    def __init__(self):
        self.val = 0
    async def __aenter__(self):
        pass
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

async def main():
    state = MockState()
    await State.loop.fn(state)

asyncio.run(main())
