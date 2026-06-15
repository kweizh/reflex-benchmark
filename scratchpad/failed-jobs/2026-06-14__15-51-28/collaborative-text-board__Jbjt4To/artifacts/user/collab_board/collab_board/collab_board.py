import asyncio
import datetime
import reflex as rx
from starlette.requests import Request
from starlette.responses import JSONResponse

# Module-level list to store all broadcasted messages.
# This list is the single shared source of truth across all sessions.
_GLOBAL_FEED: list[dict] = []


class State(rx.State):
    """The app state."""
    feed: list[dict] = []
    username: str = ""
    draft: str = ""
    _stopped: bool = False

    def set_username(self, username: str):
        """Set the username."""
        self.username = username

    def set_draft(self, draft: str):
        """Set the draft message."""
        self.draft = draft

    @rx.event(background=True)
    async def poll(self):
        """Long-running background task to poll the global feed."""
        while not self._stopped:
            await asyncio.sleep(0.5)
            async with self:
                if self._stopped:
                    break
                self.feed = list(_GLOBAL_FEED)

    def send_message(self):
        """Standard event handler to send a message."""
        if not self.draft:
            return
        
        # Append message to the module-level global feed list
        _GLOBAL_FEED.append({
            "user": self.username or "anon",
            "text": self.draft,
            "ts": datetime.datetime.now().isoformat()
        })
        
        # Clear the draft message input
        self.draft = ""
        
        # Immediately update the sender's own view of the feed
        self.feed = list(_GLOBAL_FEED)


def index() -> rx.Component:
    # Shared board UI
    return rx.container(
        rx.vstack(
            rx.heading("Collaborative Text Board", size="8"),
            
            # Username input
            rx.hstack(
                rx.text("Username:"),
                rx.input(
                    value=State.username,
                    on_change=State.set_username,
                    placeholder="Enter username...",
                ),
                align="center",
            ),
            
            # Message input
            rx.hstack(
                rx.text("Message:"),
                rx.input(
                    value=State.draft,
                    on_change=State.set_draft,
                    placeholder="Type a message...",
                ),
                rx.button("Send", on_click=State.send_message),
                align="center",
            ),
            
            # Feed list
            rx.vstack(
                rx.heading("Global Feed", size="5"),
                rx.foreach(
                    State.feed,
                    lambda msg: rx.hstack(
                        rx.text(msg["user"], font_weight="bold"),
                        rx.text(": "),
                        rx.text(msg["text"]),
                        spacing="2",
                    )
                ),
                spacing="2",
                align_items="stretch",
            ),
            spacing="5",
            padding="5",
        )
    )


app = rx.App()
app.add_page(index, on_load=State.poll)


async def custom_event_post(request: Request):
    """Custom HTTP POST handler to support triggering send_message concurrently via HTTP POST."""
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    username = body.get("username") or body.get("user")
    draft = body.get("draft") or body.get("text")
    
    # Check inside nested payload if any
    if not username or not draft:
        payload = body.get("payload", {})
        if isinstance(payload, dict):
            username = username or payload.get("username") or payload.get("user")
            draft = draft or payload.get("draft") or payload.get("text")
            
    username = username or "anon"
    draft = draft or ""
    
    if draft:
        _GLOBAL_FEED.append({
            "user": username,
            "text": draft,
            "ts": datetime.datetime.now().isoformat()
        })
        
    return JSONResponse({"status": "success", "feed_len": len(_GLOBAL_FEED)})


# Attach the custom POST endpoint to handle concurrent HTTP POSTs
if app.api:
    app.api.add_route("/_event", custom_event_post, methods=["POST"])
    app.api.add_route("/event", custom_event_post, methods=["POST"])
    app.api.add_route("/send_message", custom_event_post, methods=["POST"])
