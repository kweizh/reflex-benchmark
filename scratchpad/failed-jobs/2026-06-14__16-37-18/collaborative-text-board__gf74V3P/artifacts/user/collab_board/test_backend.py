import asyncio
import httpx
import sys

async def send_event(client, text, username):
    payload = {
        "events": [
            {
                "name": "state.send_message",
                "router_data": {"pathname": "/", "query": {}},
                "payload": {}
            }
        ],
        "state": {
            "state": {
                "username": username,
                "draft": text,
                "feed": [],
                "_stopped": False
            }
        }
    }
    # We need to simulate the event. Wait, the payload format might be different for reflex.
    # It might be simpler to just use the UI if we could, or we can just let the acceptance test do it.
    pass

