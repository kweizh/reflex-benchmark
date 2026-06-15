# Reflex Async Paginated User Directory

## Background
Reflex is a full-stack Python framework that compiles Python UI definitions into a Next.js/React frontend driven by a FastAPI/websocket backend. State is held in `rx.State` subclasses, and database models are declared with `rx.Model` (a SQLModel wrapper). Long-running database queries should be executed in background events (`@rx.event(background=True)`) using the async session helper `rx.asession()`, while UI mutations are guarded by `async with self:` to acquire the exclusive state lock.

Your task is to implement a Reflex application that serves a paginated user directory backed by SQLite. The app must seed the database with sample users at startup, expose a background event that loads one page at a time using `OFFSET`/`LIMIT`, and render the current page in a table with Prev/Next pagination controls.

## Requirements
- Define a database model `class User(rx.Model, table=True)` with at least the string fields `username` and `email`.
- On application startup (via an `on_load` event), seed the `user` table with **at least 50 distinct users** when the table is empty. Re-running the app must not duplicate the seed data.
- Implement a state class that exposes the synchronized vars `page: int = 1`, `page_size: int = 10`, and `users: list[User] = []`.
- Implement a background event handler named `fetch_page` decorated with `@rx.event(background=True)`. It must:
  - Open `rx.asession()` with `async with rx.asession() as ...`.
  - Execute a SELECT against the `User` table with `OFFSET` and `LIMIT` derived from `page` and `page_size`.
  - Assign the resulting rows to `self.users` inside an `async with self:` block.
- Render the index page at route `/` containing:
  - A table populated from `users` showing username and email for the current page.
  - A "Prev" button that decrements `page` (not below 1) and re-triggers `fetch_page`.
  - A "Next" button that increments `page` and re-triggers `fetch_page`.
- Use `uv` to manage the Python environment. The project must be initialized with the blank Reflex template and the SQLite migrations must be generated and applied so the `user` table exists in `reflex.db` (or whichever path is configured).

## Implementation Hints
- Bootstrap the project with `uv init`, `uv add reflex`, and `uv run reflex init --template blank`.
- After defining the model, run `uv run reflex db init`, `uv run reflex db makemigrations --message "initial schema"`, and `uv run reflex db migrate` so the SQLite schema matches the model.
- Inside `fetch_page`, you can build the statement with `User.select().offset(...).limit(...)` or `sqlmodel.select(User).offset(...).limit(...)`, await it via `await asession.execute(stmt)`, and materialise the rows (for example `[row[0] for row in result.all()]`) before mutating state.
- Remember: background events cannot mutate `self.*` outside of `async with self:`; do the I/O outside the lock and only assign the materialised list inside it.
- The Prev/Next buttons should call event handlers that update `page` and then dispatch `fetch_page` (e.g., by `yield`/`return`ing the background event).
- Wire the index page so it triggers `fetch_page` on page load via the `rx.App` `on_load` mechanism or `rx.page(on_load=...)` so the first page renders without manual interaction.
- The frontend bundle is produced by `uv run reflex export --frontend-only --no-zip`; the resulting static assets (under `.web/_static` or similar) must contain the string bindings for `users`, `page`, `page_size`, and the literal button labels `Prev` and `Next`.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- Use `uv` for all Python operations. Reflex must be installed only inside the `uv` project; do not assume system Python has access to it.
- The application source must include a top-level `class User(rx.Model, table=True)` declaration with at least the string fields `username` and `email`.
- The application source must contain at least one `@rx.event(background=True)` handler that uses `async with rx.asession()` and `async with self:` and references the `page`, `page_size`, and `users` state vars.
- After running `uv run reflex db init`, `uv run reflex db makemigrations --message "initial schema"`, and `uv run reflex db migrate`, a SQLite database file must exist (default: `/home/user/myproject/reflex.db`) and contain a table named `user` with at least the columns `id`, `username`, `email`.
- Start command (long-running): `cd /home/user/myproject && uv run reflex run --env dev --loglevel info`
  - Frontend port: 3000
  - Backend port: 8000
  - Route `/` must render a table layout and the literal button labels `Prev` and `Next`.
- The exported frontend produced by `uv run reflex export --frontend-only --no-zip` must contain string references to `users`, `page`, and `page_size` as well as the literal labels `Prev` and `Next` somewhere under the project's exported web assets.
- After verification the executor must stop all background Reflex servers (frontend on :3000 and backend on :8000) it started, so the ports are free.

