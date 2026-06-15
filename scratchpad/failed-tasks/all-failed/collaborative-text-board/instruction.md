# Collaborative Text Board with Reflex Background Tasks

## Background
Build a small Reflex web application that acts as a **shared text board**. Every connected client should be able to type a message and immediately see other clients' messages appear in a global feed. The feed is kept in sync by a long-running background task that polls a shared in-memory store and pushes updates back to each client's state.

This task exercises Reflex's `@rx.event(background=True)` decorator, the `async with self` state-locking pattern, module-level shared state across user sessions, backend-only state vars (prefixed with `_`), and `on_load` page hooks.

## Requirements
- Implement a Reflex application named `collab_board` with a single page at `/` that renders the shared board UI.
- Store the broadcasted messages in a **module-level Python list** (e.g. `_GLOBAL_FEED: list[dict]`) declared at the top of the state module. This list is the single shared source of truth across all client sessions and **must not** be a state attribute.
- Each entry in `_GLOBAL_FEED` is a dict with the keys `user`, `text`, and `ts` (string ISO timestamp or float epoch — anything JSON-serializable).
- The Reflex state class must expose at least these fields:
  - `feed: list[dict] = []` — the per-client view of the feed, synchronized to the browser.
  - `username: str = ""` — the name typed in the username input.
  - `draft: str = ""` — the current value of the message input.
  - `_stopped: bool = False` — a **backend-only** flag (note the leading underscore) used to stop the polling loop.
- Implement a background event handler decorated with `@rx.event(background=True)` (commonly named `poll`). It must:
  - `await asyncio.sleep(0.5)` **outside** the `async with self:` block.
  - Enter `async with self:` and copy a snapshot of the module-level list into `self.feed` (e.g. `self.feed = list(_GLOBAL_FEED)`).
  - Break the loop when `self._stopped` becomes `True`.
- Implement a standard event handler `send_message(self)` that appends `{"user": self.username or "anon", "text": self.draft, "ts": ...}` to the module-level `_GLOBAL_FEED` list, clears `self.draft`, and triggers a refresh so the sender's own view updates promptly. The handler must mutate `_GLOBAL_FEED` (not `self.feed`).
- The page must register the polling background task via the page's `on_load` hook so it starts automatically when a client opens `/`.
- The UI must contain:
  - A text input bound to `username`.
  - A text input bound to `draft`.
  - A button labelled **Send** that triggers `send_message`.
  - A list of messages rendered with `rx.foreach(State.feed, ...)` so each new entry shows the user and the text.

## Implementation Hints
- Use the project layout produced by `uv run reflex init --template blank`. The state and page live under `collab_board/collab_board.py`.
- Module-level state (a Python `list` declared at module scope) is shared across all client websocket sessions in a single Reflex backend process — this is exactly what makes "collaboration" work in this task.
- `@rx.event(background=True)` requires `async with self:` to mutate state; any direct write outside the block raises `ImmutableStateError`. Keep I/O / `asyncio.sleep` outside the lock.
- Wire the polling task to the page using the `on_load` parameter of `@rx.page` or `app.add_page(..., on_load=State.poll)`.
- `rx.foreach` is required to render lists driven by reactive state — Python `for` loops do not work.
- Use `uv` to manage the Python environment (`uv init`, `uv add reflex`, `uv run reflex init --template blank`, `uv run reflex run`).
- Reflex must be started on the default ports (frontend `3000`, backend `8000`).

## Acceptance Criteria
- Project path: `/home/user/collab_board`
- Start command: `cd /home/user/collab_board && uv run reflex run --loglevel info`
- Port: `3000` (frontend) and `8000` (backend) — both must be reachable.
- The application must expose a `State` (subclass of `rx.State`, any name) with:
  - A base var `feed: list[dict]` initially `[]`.
  - A base var `username: str` initially `""`.
  - A base var `draft: str` initially `""`.
  - A backend-only var `_stopped: bool` (name starts with a single underscore).
- A module-level list named `_GLOBAL_FEED` (or `GLOBAL_FEED`) defined at module scope inside the state module and read/written from event handlers.
- A background event handler must be decorated with `@rx.event(background=True)`, contain `async with self:` and an `asyncio.sleep(...)` call. It loops until the backend-only `_stopped` flag is set.
- A standard (non-background) event handler `send_message` must mutate the module-level `_GLOBAL_FEED` list (e.g. `_GLOBAL_FEED.append(...)`).
- The page at `/` must register `on_load=` that triggers the polling background task.
- The compiled frontend (`.web/pages/index.js` or `.web/pages/index.jsx`) must contain a **Send** button label and must render the feed using `rx.foreach(State.feed, ...)` (the compiled output will contain a `.map(` call over the feed var).
- When the backend is running, two concurrent HTTP POSTs to the backend event endpoint that call `send_message` must result in two entries appearing in `_GLOBAL_FEED` (verified through a Python helper that imports the state module directly).
- After verification, all background `reflex` processes (frontend + backend) must be killable; tests are responsible for tearing them down.

