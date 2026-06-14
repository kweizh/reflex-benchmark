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
    # create event processor
    app._setup_event_processor()
    
    token = "api"
    # To process an event, we create an Event object
    from reflex.event import Event
    event = Event(token=token, name="state.loop", router_data={})
    
    # Process it
    async for update in app.event_processor.process(event):
        pass

asyncio.run(main())
