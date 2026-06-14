import reflex as rx
import asyncio
from reflex.istate.manager.token import BaseStateToken

class State(rx.State):
    val: int = 0
    @rx.event(background=True)
    async def loop(self):
        async with self:
            self.val += 1
            print("Loop ran, val:", self.val)

app = rx.App()

async def main():
    app._setup_state()
    token = BaseStateToken(ident="api", cls=State)
    
    # get_state creates it if missing?
    state = await app.state_manager.get_state(token)
    print("State initialized:", state is not None)
    
    # Call the fn
    await State.loop.fn(state)
    
    async with app.modify_state(token) as state:
        print("Final val:", state.val)

asyncio.run(main())
