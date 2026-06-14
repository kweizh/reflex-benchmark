# CSV Upload + Async Processing Pipeline with Progress

## Background
Build a Reflex web application that lets a user upload a CSV file of people records, parses it asynchronously in the background, validates each row, inserts valid rows into a SQLite database via Reflex's ORM, and reports per-row progress and a final summary back to the UI without ever blocking the event loop or raising `ImmutableStateError`.

## Requirements
- A single-page Reflex app served at `/` that contains an `rx.upload` component (single CSV file, `text/csv` only) and a button (or `on_drop` trigger) that submits the selected file.
- Persist valid records to SQLite via `rx.Model` + `rx.asession` (the default `sqlite:///reflex.db` connection is fine).
- Process the uploaded CSV in a `@rx.event(background=True)` async handler. All mutations of synchronized state vars must occur inside `async with self:` blocks. Heavy work (reading the file, parsing, DB I/O) must not hold the state lock continuously.
- Maintain the following base state vars on the State class and keep them synchronized with the UI:
  - `progress: int` in the range 0..100
  - `valid_count: int`
  - `invalid_count: int`
  - `errors: list[str]`
- The UI must visibly render a progress bar bound to `progress` and a final summary line that includes the valid and invalid row counts after processing completes.

## Implementation Hints
- Use `uv` to manage the Python environment (see `Acceptance Criteria` for exact commands). Reflex must be initialized non-interactively with `--template blank`.
- The default DB URL `sqlite:///reflex.db` resolves to `/home/user/myproject/reflex.db` when the app is run from the project root.
- Remember the four rules of background events: must be `async`, must use `async with self:` to mutate state, may read stale state outside the lock, and must not be called directly from other handlers.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- Environment manager: `uv` (the project must include a `pyproject.toml` and a working `uv` lock such that `uv run reflex run` works from a clean checkout).
- Start command (run from the project path): `uv run reflex run --loglevel info`
  - Frontend port: `3000`
  - Backend port: `8000`
- Database file: `/home/user/myproject/reflex.db`
- Routes / UI:
  - `GET /` returns the page with an `rx.upload` dropzone (id `csv_upload`, `accept={"text/csv": [".csv"]}`, `multiple=False`), an upload trigger control (button), a progress bar visualizing `State.progress`, and a summary text element.
- Database schema:
  - A table created from an `rx.Model` subclass with at least these columns: `name: str`, `email: str`, `age: int` (an autoincrement `id` primary key is acceptable in addition).
  - The schema must be initialized via `reflex db init` + `reflex db makemigrations` + `reflex db migrate` so that the table exists before the app first serves a request.
- CSV contract:
  - The first non-empty line must be the header `name,email,age` (case-sensitive, exact order). Header mismatch is a fatal upload error and must NOT insert any rows.
  - Each subsequent row is **valid** iff it has exactly 3 comma-separated fields AND `name` is non-empty AND `email` contains an `@` AND `age` parses as a strictly positive integer (`int(age) > 0`).
  - Any other row is **invalid** and must NOT be inserted. The 1-based row number (counting from the header as row 1; data rows start at row 2) must appear in at least one entry of `State.errors`.
- Progress contract:
  - At the start of processing `progress` MUST be set to `0`.
  - When processing completes successfully `progress` MUST be exactly `100`.
  - `valid_count + invalid_count` MUST equal the number of data rows processed.
- Summary contract:
  - After processing, a visible element on the page must contain the exact substring `Processed <T> rows: <V> valid, <I> invalid` where `<T>`, `<V>`, `<I>` are the integer counts (e.g. `Processed 8 rows: 5 valid, 3 invalid`).
- Stability contract:
  - The backend log must not contain any `ImmutableStateError` while a CSV is being processed.
  - Re-uploading the same file twice must result in the per-upload counts being correct for each upload (the app is free to either reset counts on each new upload or accumulate, but the summary text after each upload must accurately reflect the contents just processed).
- Reflex Cloud / external services: none required.
- Teardown: any background dev server started during development MUST be stopped before the task is considered complete. The verifier will start its own server.

