# Reflex Background File Hash Worker

## Background
Build a single-page [Reflex](https://reflex.dev) application that computes SHA-256 hashes for a batch of locally-generated records using a non-blocking background task. The UI must stay responsive while the worker runs, report per-item and overall progress in real time, and support cooperative cancellation. Everything runs locally: there are no external services, APIs, databases, or network calls.

## Requirements
- A page at route `/` that shows:
  - A heading whose text contains `File Hash Worker`.
  - An overall progress indicator and a status label reflecting the current phase.
  - A `Start` button that launches the hashing run and a `Cancel` button that requests cancellation.
  - A per-record list rendered from state that shows each record's name and (once computed) its hash.
- A long-running hashing worker implemented as a Reflex background task that iterates the batch, hashing one record at a time, and updates the per-record result and the overall progress as it goes so the UI reflects progress incrementally.
- Cooperative cancellation: the `Cancel` button sets a backend-only flag that the worker checks each iteration and, when set, stops the loop cleanly (partially completed results are kept) and reports a cancelled status.
- A guard that prevents a second run from starting while one is already in progress (clicking `Start` again must not launch a duplicate concurrent worker).
- Derived, read-only values for the overall percent complete (an integer from 0 to 100) and a status string that is exactly one of `Idle`, `Running`, `Cancelled`, or `Done`.

## Implementation Hints
- Use `uv` to manage the Python environment (`uv init`, `uv add reflex`, `uv run reflex init --template blank`, `uv run reflex run`). Some Reflex dependencies conflict with system packages, so do not install Reflex into the system Python.
- Define the worker with `@rx.event(background=True)`; it must be an `async` method and may only mutate state inside an `async with self:` block. Keep the actual hashing/CPU work and any `await` points outside the lock so the UI stays responsive.
- Backend-only state vars (names beginning with an underscore) are not serialized to the client; use them for the cancellation flag and the in-progress guard.
- Expose percent complete and the status string as computed vars (`@rx.var`).
- Render the per-record rows with `rx.foreach` over a state list; use `rx.cond` where you need conditional UI.
- Put the deterministic record generation and hashing in a plain-Python module so the logic is testable without Reflex. Create a file at the project root `/home/user/hashworker/hash_core.py` that imports nothing from Reflex and exposes exactly these two functions, which your Reflex state must import and use:
  - `generate_records(count: int, seed: str) -> list[dict]`: returns a list of exactly `count` dicts, each having exactly the keys `name` (str) and `content` (str). The output must be deterministic for a given `(count, seed)` pair, and different seeds must produce different content.
  - `hash_record(content: str) -> str`: returns the lowercase hex SHA-256 digest of `content` encoded as UTF-8.
- Project path: `/home/user/hashworker`
- Start command: `uv run reflex run` (run it from the project path)
- Ports: frontend `3000`, backend `8000`
- After you finish building and verifying, you MUST stop/kill every background server or process you started (for example any `reflex run` process) so that ports 3000 and 8000 are free. The grader starts its own server.

