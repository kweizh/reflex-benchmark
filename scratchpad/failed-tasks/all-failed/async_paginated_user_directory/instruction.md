# Async Paginated User Directory with Search (Reflex)

## Background

Build a Reflex application that renders a paginated, searchable user directory backed by a SQLite database (`rx.Model`). User rows are fetched asynchronously inside a background event handler that takes the State lock to mutate observable variables. The UI must support paging forward/backward, a case-insensitive contains-match search on the username column, and an indicator of the total number of pages.

## Requirements

- A `User` SQL model (subclass of `rx.Model`, `table=True`) with at least `username: str` and `email: str` columns.
- A Reflex `State` whose synchronized base vars include: the current `page` (1-indexed), the `page_size`, the `search_query` (string), the `users` of the current page, and the `total_users` matching the current filter.
- A `total_pages` value (computed or stored) derived from `total_users` and `page_size`.
- A background event handler decorated with `@rx.event(background=True)` that:
  - Reads the current `search_query`, `page`, and `page_size` under the State lock.
  - Opens `rx.asession()` and issues a single paginated SELECT that respects an offset/limit and a case-insensitive contains-match on `username`.
  - Computes the total matching rows for the current search filter.
  - Re-enters `async with self:` exactly once to publish `users`, `total_users`, and `total_pages` together.
- A UI on the index route (`/`) showing the users for the current page, a search input bound to `search_query`, Previous/Next buttons that change `page`, and a visible total-pages indicator (e.g. `Page X of Y`).
- A seeding mechanism that ensures the database always contains exactly the 47 fixture users described under Acceptance Criteria after `reflex db migrate` has run.
- A non-Reflex CLI helper `probe.py` at the project root that exercises the same query path and prints the result as JSON, so the verifier can confirm pagination/search semantics without driving the websocket UI (see Acceptance Criteria for the exact contract).

## Implementation Hints

- Use the project setup flow from the research plan (`uv init`, `uv add reflex`, `uv run reflex init --template blank`, `uv run reflex db init/makemigrations/migrate`). Keep all Python deps inside the `uv`-managed virtual environment; the verifier will invoke Python through `uv run`.
- Page size must be exactly 10 and must not be configurable from the client.
- Inside the background handler, only acquire the State lock (`async with self:`) around reads of inputs and around the publication of results. Do not call `rx.asession()` while holding the lock.
- For the case-insensitive contains-match, choose a SQLAlchemy/SQLModel construct that works against SQLite (e.g. `ilike`, `func.lower(...).contains(...)`, or an equivalent). The matching is on `username` only.
- `total_pages` must be `ceil(total_users / page_size)` when `total_users > 0` and `0` when `total_users == 0`.
- `probe.py` must use the same `rx.Model` and the same query construction as the background handler (factor a shared async function if helpful). It must be invokable via `uv run python probe.py ...` and must not start the Reflex web server.
- After you have finished developing, **kill all background servers** you started (e.g. `uv run reflex run`). The verifier starts the server itself.

## Acceptance Criteria

- Project path: `/home/user/myproject`
- Start command: `cd /home/user/myproject && uv run reflex run --loglevel info`
- Frontend port: `3000`
- Backend port: `8000`
- Database: SQLite at `/home/user/myproject/reflex.db`, with a `user` table containing exactly 47 rows after migration + seeding. Re-running the seeder must remain idempotent (total rows stay at 47).
- Pagination contract enforced by `probe.py`:
  - Command: `cd /home/user/myproject && uv run python probe.py --page <N> [--search <S>]`
  - Stdout must be a single JSON object on its own line with the schema:
    ```json
    {
      "page": <int>,
      "page_size": 10,
      "total_users": <int>,
      "total_pages": <int>,
      "items": [
        {"id": <int>, "username": <string>, "email": <string>}
      ]
    }
    ```
  - `items` lists the rows for the requested page in ascending `id` order after applying the optional search filter.
  - `total_users` is the count of rows matching the filter (or 47 when no filter is provided).
  - `total_pages` is `ceil(total_users / 10)` when `total_users > 0`, and `0` when `total_users == 0`.
  - When `page` is beyond `total_pages`, `items` is an empty array (the other fields are still populated correctly).
  - The search filter is a case-insensitive contains-match on `username`.
- UI contract on `http://localhost:3000/`:
  - The page renders without compile or runtime errors.
  - It contains a search input, a Previous and a Next control, and a text indicator of the form `Page <current> of <total>`.
  - The current page's users are listed (showing at least their `username`).
- State-lock contract:
  - The background handler decorated with `@rx.event(background=True)` mutates `users`, `total_users`, and `total_pages` only inside an `async with self:` block.
  - Invoking the directory query path (via `probe.py` or the UI) must not raise `reflex.utils.exceptions.ImmutableStateError`.
- Background processes: After implementation, all `reflex run` (or other) background servers you started must be terminated before the verifier runs.

