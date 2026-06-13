You are building an AI chat interface that requires real-time, typewriter-style streaming of text chunk responses to avoid high UI latency while waiting for the full response.

You need to write an event handler that simulates streaming by incrementally appending text chunks to a `chat_response` state variable while toggling an active loading spinner.

**Constraints:**
- You MUST use the `yield` keyword to incrementally stream state updates to the frontend.
- Do NOT use `@rx.event(background=True)` for this specific generator-based streaming behavior.
- Ensure an `is_loading` boolean state variable is toggled to `True` at the start of the generator and `False` before the final yield.