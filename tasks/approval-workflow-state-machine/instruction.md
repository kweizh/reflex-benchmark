# Document Approval Workflow (Reflex State Machine)

## Background
Build a full-stack **Reflex** (pure-Python) web application that models a document approval workflow as a finite state machine. The app tracks a single document through review stages, renders a different UI for each stage, guards which transitions are legal, rejects illegal transitions with an error message, and keeps an append-only audit log persisted in a local SQLite database.

## Requirements
Project path: `/home/user/approval_app`. Initialize a **blank** Reflex app here; the Reflex app name must be `approval_app`.

Workflow states (use these exact strings): `Draft`, `Submitted`, `UnderReview`, `Approved`, `Rejected`.

Allowed transitions, expressed as `action -> resulting state`, grouped by the current state:
- From `Draft`: `submit` -> `Submitted`
- From `Submitted`: `start_review` -> `UnderReview`; `recall` -> `Draft`
- From `UnderReview`: `approve` -> `Approved`; `reject` -> `Rejected`
- From `Rejected`: `revise` -> `Draft`
- From `Approved`: terminal state, no actions allowed

Behavior:
- The app manages a single document seeded with title `Design Proposal` and initial state `Draft`.
- Applying a **legal** action changes the document state and appends exactly one row to the audit log.
- Applying an **illegal** action (any action that is not allowed from the current state) must be rejected: the document state must not change, no audit row may be added, and a human-readable error message must be produced.
- The audit log is **append-only**: rows are only ever inserted, never updated or deleted during normal operation.

Persistence (local SQLite, via `rx.Model`). Keep the default Reflex database file `reflex.db` at the project root (`/home/user/approval_app/reflex.db`):
- Table `document` with at least the columns `id`, `title`, `state`.
- Table `auditlogentry` with at least the columns `id`, `from_state`, `to_state`, `action`, `timestamp`. `timestamp` is an ISO-8601 string recorded at the moment the transition is applied.

Web UI (Reflex):
- Use `rx.match` on the current state to render a distinct panel per state (for example: `Draft` shows a submit control; `UnderReview` shows approve/reject controls; `Approved` shows a success banner; `Rejected` shows a revise control).
- Expose the currently allowed actions through a computed var and display them.
- Render the full audit log using `rx.foreach`.
- Display the error message when an illegal action is attempted.
- The event handlers that perform transitions must be guarded so illegal transitions are rejected as described above.

Automation CLI:
- Provide a rerunnable module `approval_app.workflow_cli` that operates on the **same** SQLite database as the web app and shares the **same** transition rules and audit-logging behavior (do not duplicate divergent logic).

## Implementation Hints
- Use `uv` to manage the Python environment: `uv init`, `uv add reflex`, then `uv run reflex init --template blank`, then the `reflex db` migration commands (`db init` / `db makemigrations` / `db migrate`) to create the SQLite tables before running.
- Keep the transition table and the "apply a transition" logic in a single shared module so both the Reflex event handlers and the CLI use identical behavior; treat the SQLite database as the single source of truth for the current state (so the web app and the CLI always agree).
- `rx.match` fits the per-state UI; a cached computed var fits the "allowed actions" list; `rx.foreach` fits rendering the audit rows.
- Web app start command: `uv run reflex run` (frontend on port 3000, backend on port 8000).
- CLI contract (exit codes and stdout are checked exactly):
  - `uv run python -m approval_app.workflow_cli status` -> prints two lines: `State: <state>` on the first line and `Allowed: <comma-separated action names, or empty>` on the second line.
  - `uv run python -m approval_app.workflow_cli apply <action>` -> on a legal action, exit code 0 and stdout contains `OK: <from_state> -> <to_state>`; on an illegal action, exit code 1 and stdout contains `ERROR: <message>`.
  - `uv run python -m approval_app.workflow_cli reset` -> resets the document back to `Draft`, clears the audit log, exit code 0.
- IMPORTANT: After you finish and verify your work, **kill every background server/process you started** (for example the `uv run reflex run` dev server) so nothing keeps ports 3000 or 8000 open. The final evaluation starts its own server.

