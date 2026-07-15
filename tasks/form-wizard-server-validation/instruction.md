# Multi-Step Registration Wizard with Server-Side Validation (Reflex)

## Background
Build a full-stack **Reflex** (pure-Python web framework) application: a 3-step registration wizard. Every step is validated on the server. The `Next` button only advances to the following step when the current step's server-side validation passes; otherwise per-field error messages are shown and the wizard stays on the current step. On the final step, a successful submission aggregates all collected fields and writes one record to a local SQLite database.

The project uses the Astral `uv` package manager to manage the Python environment (Reflex has dependencies that conflict with system packages, so `uv` is mandatory).

## Requirements
- A Reflex app implementing a wizard with exactly 3 ordered steps:
  - Step 1 — Account: an `email` field.
  - Step 2 — Security: a `password` field and a `confirm_password` field.
  - Step 3 — Confirmation: a `full_name` field and an `accept_terms` boolean (checkbox).
- A `Next` button that runs the current step's server-side validation. If validation fails, it must NOT advance and must render the failing field error(s) next to the corresponding field(s). A `Back` button returns to the previous step.
- On the final step, submitting runs step-3 validation and, when it passes, persists a single aggregated record to a local SQLite database.
- Two computed vars derived from the current step: a human-readable step label and a numeric progress percentage.
- Conditional rendering (`rx.cond`) is used to switch between step layouts and to show/hide per-field error messages.

## Implementation Hints
- Use `uv` to create the environment and add Reflex, then initialize non-interactively with the blank template (`uv run reflex init --template blank`). Run the app with `uv run reflex run`.
- Keep the server-side validation logic and the SQLite persistence logic in plain Python modules (no Reflex imports) so they are reusable and independently importable, and have the Reflex `State` event handlers call into them. The `Next`/submit event handler should be *guarded*: only advance the step (or persist) when validation returns no errors. Store per-field errors in a `dict` state var and render them with `rx.cond`. Use `@rx.var` computed vars for the step label and progress.
- Project path: `/home/user/registration_wizard` (the `uv` project root). Create the wizard app package inside this directory.
- **Required helper module `validators.py`** at the project root (`/home/user/registration_wizard/validators.py`), importable with a plain `python3` and importing NO Reflex, exposing:
  - `validate_step(step: int, data: dict) -> dict` — `step` is `1`, `2`, or `3`; `data` may contain the keys `email`, `password`, `confirm_password`, `full_name`, `accept_terms`. It returns a dict mapping each invalid field name to an error message string, and an empty dict `{}` when the step is valid. The exact rules and error strings are:
    - Step 1 validates key `email`: blank/whitespace → `"Email is required"`; otherwise not a valid email address (must have a single `@` with a non-empty local part and a domain containing at least one dot) → `"Invalid email address"`.
    - Step 2 validates keys `password` and `confirm_password`: for `password`, in this order — fewer than 8 characters → `"Password must be at least 8 characters"`, else no uppercase letter → `"Password must contain an uppercase letter"`, else no lowercase letter → `"Password must contain a lowercase letter"`, else no digit → `"Password must contain a digit"`; for `confirm_password`, when it does not equal `password` → `"Passwords do not match"`.
    - Step 3 validates keys `full_name` and `accept_terms`: blank/whitespace `full_name` → `"Full name is required"`; falsy `accept_terms` → `"You must accept the terms"`.
  - **Required helper module `db.py`** at the project root (`/home/user/registration_wizard/db.py`), importable with a plain `python3` and using only the standard library, exposing:
    - `DB_PATH` — a module-level string pointing to a SQLite file named `registration.db` located in the project root directory.
    - `init_db(db_path=DB_PATH) -> None` — creates (if absent) a table named `registrations` with columns `id` (INTEGER primary key autoincrement), `email` (TEXT not null), `full_name` (TEXT not null), `password_hash` (TEXT not null), and `created_at` (TEXT not null).
    - `insert_registration(email, full_name, password, db_path=DB_PATH) -> int` — inserts one row, storing `password_hash` as the SHA-256 hex digest of `password` and `created_at` as an ISO-8601 UTC timestamp, and returns the new row's integer `id`.
  - The Reflex `State` must import and use both `validate_step` (in the guarded step-advance/submit handler) and `insert_registration` (on successful final submit), and must call `init_db` so the `registrations` table exists once the app has started.
- The app runs as a long-running dev server: Start command `uv run reflex run` (run from `/home/user/registration_wizard`), frontend Port `3000`, backend Port `8000`. The backend health route `http://localhost:8000/ping` returns `pong`. The browser page at `http://localhost:3000` must have the HTML document title `Registration Wizard`.
- **After you finish and verify your work, you MUST kill every background server/process you started (e.g. the Reflex dev server on ports 3000 and 8000) so no server is left running.** The final verification will start its own server as needed.

