# Background-Polling Job Queue Dashboard (Reflex)

## Background

Build a Reflex application that runs a **background polling worker** to process queued jobs persisted in SQLite. End users submit jobs from a dashboard; a long-lived `@rx.event(background=True)` polling task ticks roughly once per second, claims the oldest PENDING job, advances it through a fixed number of work steps while updating its `progress`, and finally marks it COMPLETED. The dashboard shows a live table of all jobs and a status-count summary that is implemented as a **cached** computed var.

## Requirements

- A `Job` SQL model (subclass of `rx.Model`, `table=True`) with at least:
  - `id: int` (auto primary key)
  - `name: str`
  - `status: str` (one of `PENDING`, `RUNNING`, `COMPLETED`)
  - `progress: int` (in the inclusive range `[0, 100]`)
  - `created_at: datetime.datetime` (UTC timestamp at insertion time)
- A Reflex `State` whose synchronized base vars include a list of jobs that is rendered live in the UI.
- A **cached** computed var (declared with `@rx.var(cache=True)`) that returns the per-status counts (counts for at least `PENDING`, `RUNNING`, and `COMPLETED`) derived from the in-memory job list.
- A background polling event handler decorated with `@rx.event(background=True)` that:
  - Runs an indefinite loop, sleeping roughly 1 second between iterations.
  - On each iteration, claims the oldest `PENDING` job (lowest `id`).
  - Transitions the claimed job through exactly the progress sequence `20 -> 40 -> 60 -> 80 -> 100` (5 steps). The `status` must be `RUNNING` while progress is strictly less than `100`, and `COMPLETED` once progress reaches `100`.
  - Persists every status/progress transition to SQLite so an external observer can witness the transitions.
  - Mutates Reflex state vars (e.g. the in-memory job list) **only** inside `async with self:` blocks and **never** outside of them.
  - Re-fetches the current job list from SQLite and publishes it to the synchronized state so the dashboard updates live.
- A submit action wired to the dashboard UI that inserts a new row with `status='PENDING'` and `progress=0` into the database.
- A custom FastAPI router mounted on the Reflex backend through the `api_transformer` parameter of `rx.App`, exposing exactly the following JSON endpoints (see the Acceptance Criteria for the response schema):
  - `POST /api/jobs` to enqueue a new PENDING job.
  - `GET /api/jobs` to list all jobs.
  - `GET /api/jobs/counts` to return the per-status counts derived from the database.
- An index page at `/` rendering:
  - A name input plus a submit control that invokes the submit action.
  - A status-count summary that reads from the cached computed var.
  - A table of jobs (rendered with `rx.foreach`) showing at least `id`, `name`, `status`, and `progress` columns.
- The background polling worker must start automatically on app load (e.g. by an `on_load` event on the index page, or any other supported Reflex mechanism). The verifier will only start the Reflex server and exercise the HTTP API; it will not invoke any state event by hand.

## Implementation Hints

- Use the project setup flow from the research plan (`uv init`, `uv add reflex`, `uv run reflex init --template blank`, `uv run reflex db init/makemigrations/migrate`). Keep all Python dependencies inside the `uv`-managed virtual environment.
- Use `rx.asession()` (the async session) inside the background event handler. Do not call `rx.asession()` while holding the state lock; perform DB I/O outside `async with self:`.
- Guard against duplicate polling workers: starting the worker on every page load should not result in N concurrent workers stepping on each other. A backend-only flag (a Python attribute prefixed with `_`) or an equivalent guard inside the state is sufficient.
- The status count computed var must use `@rx.var(cache=True)` and derive its value from a synchronized state var (e.g. the in-memory job list), not from a fresh database query, so the framework can cache it.
- Use the `api_transformer` argument of `rx.App` to mount your `FastAPI()` instance with the three routes above. The routes share the same SQLite database as the Reflex state.
- Keep each tick of the polling loop reasonably short so that PENDING jobs do not languish in the queue; the verifier requires that a freshly enqueued PENDING job reach COMPLETED within a small bounded number of seconds.
- After you have finished developing, **kill all background servers** you started (e.g. `uv run reflex run`). The verifier starts its own Reflex server.

## Acceptance Criteria

- Project path: `/home/user/myproject`
- Start command: `cd /home/user/myproject && uv run reflex run --loglevel info`
- Frontend port: `3000`
- Backend port: `8000`
- Database: SQLite at `/home/user/myproject/reflex.db`. The job table must be created by `reflex db migrate` (no manual seed data is required; the table must start empty after migration on a fresh DB).
- HTTP API contract (mounted via `api_transformer`):
  - `POST http://localhost:8000/api/jobs`
    - Request body: JSON object `{"name": <string>}`. The string must be non-empty; otherwise the endpoint returns HTTP 4xx.
    - Response body on success: JSON object `{"id": <int>, "name": <string>, "status": "PENDING", "progress": 0}` and HTTP 200 or 201.
    - Side effect: inserts exactly one row into the `job` table with `status='PENDING'` and `progress=0`.
  - `GET http://localhost:8000/api/jobs`
    - Response body: JSON array, sorted by `id` ascending. Each element has the shape `{"id": <int>, "name": <string>, "status": <string>, "progress": <int>}`.
  - `GET http://localhost:8000/api/jobs/counts`
    - Response body: JSON object with at least the keys `PENDING`, `RUNNING`, `COMPLETED`, each mapped to a non-negative integer. The sum of those three counts must equal the total number of rows in the `job` table.
- Worker contract:
  - After a row is inserted with `status='PENDING'` and `progress=0`, the row must reach `status='COMPLETED'` and `progress=100` within 30 seconds.
  - While the row is being processed, `progress` is monotonically non-decreasing and passes through the values `20, 40, 60, 80, 100` in that order (each value must be observed at least once in the database before the next is written).
  - While `progress < 100`, the row's `status` must be `RUNNING` (it is acceptable for the row to be `RUNNING` with `progress=0` for a brief moment immediately after being claimed). Once `progress == 100`, the row's `status` must be `COMPLETED`.
  - The counts returned by `GET /api/jobs/counts` must always exactly reflect the database when sampled between transitions.
- UI contract on `http://localhost:3000/`:
  - The page renders without compile or runtime errors and returns HTTP 200 with a non-empty HTML document body on a GET request.
  - The page contains a name input control, a submit control, a status-count summary, and a job table rendered with `rx.foreach`.
- State-lock contract:
  - The Reflex backend log must not contain `ImmutableStateError` or `Background task StateProxy is immutable` while the verifier is running.
  - The status-count computation in the State must use `@rx.var(cache=True)` (verified by static source check).
  - The polling worker must be decorated with `@rx.event(background=True)` and must contain at least one `async with self:` block (verified by static source check).
- Background processes: After implementation, all `reflex run` (or other) background servers you started must be terminated before the verifier runs.

