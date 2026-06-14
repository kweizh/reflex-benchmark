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

@app.api.get("/test")
async def test_endpoint():
    token = BaseStateToken(ident="api", cls=State)
    async with app.modify_state(token) as state:
        # call the background event?
        # wait, background events are converted to EventHandlers, which are not methods
        pass
    return {"ok": True}

