# Background Scheduled Email Digest Generator (Reflex)

## Background
You are building a Reflex application that runs a **scheduler loop as a background event** to mock-send periodic email digests. The scheduler ticks roughly every second, scans an SQLite-backed table of digests, and for every row whose `next_due_at` is in the past it writes a row to a `SentEmail` audit table and reschedules the row's next due time. The UI shows due/queued counts and a **Force Run** button.

The hard parts of this task are:
- Time-based scheduling that produces a *bounded* number of mock sends per real-world second.
- Transactional, idempotent updates to two SQLite tables from a background coroutine (must not double-send within the same tick, must survive scheduler restarts).
- Reflex's strict rule that background events may only mutate state inside `async with self`.

## Acceptance Criteria
- Project path: `/home/user/email_scheduler`
- Start command: `cd /home/user/email_scheduler && nohup uv run reflex run --backend-only --backend-port 8000 --loglevel debug > /home/user/email_scheduler/server.log 2>&1 &`
- Port: `8000`
- Server log: `/home/user/email_scheduler/server.log` (must exist after the server has been started)
- The project must be a Reflex application initialized with the `blank` template and managed by `uv`, using SQLite (the Reflex default DB) via `rx.Model`.
- The project must define two `rx.Model` tables (any class names are fine, but the table names exposed to SQL must be `emaildigest` and `sentemail`, which is the default Reflex/SQLModel lowercasing of `EmailDigest`/`SentEmail`):
  - `emaildigest`: columns `id` (int PK), `recipient` (str), `period_seconds` (int), `last_sent_at` (float, unix seconds, nullable), `next_due_at` (float, unix seconds, required).
  - `sentemail`: columns `id` (int PK), `digest_id` (int FK to `emaildigest.id`), `recipient` (str), `sent_at` (float, unix seconds, required).
- The state class must declare at least one event handler decorated with `@rx.event(background=True)` that:
  - Loops while a backend-only flag is set,
  - Sleeps ~1 second per tick,
  - On each tick, opens a DB session, finds every `emaildigest` row whose `next_due_at <= now`, inserts one `sentemail` row per due digest with `sent_at = now`, and reschedules the digest by setting `last_sent_at = now` and `next_due_at = now + period_seconds`,
  - Holds the Reflex state lock with `async with self` whenever it writes to shared state vars (counters, etc.) and never mutates state outside that block.
- A non-background `@rx.event` handler must implement **Force Run**: when invoked, send exactly one `sentemail` row for the digest whose `next_due_at` is the earliest (regardless of whether it is due yet) and reschedule it. The Force Run handler must complete before returning control to the UI; do not delegate it to the background loop.
- HTTP API (mounted via `rx.App(api_transformer=...)`), all responses JSON with HTTP 200 unless noted. The endpoints exist so the verifier can drive and observe the scheduler without a browser; they MUST delegate to the same underlying SQLite tables and scheduler state used by the Reflex UI/state.
  - `POST /api/scheduler/seed`
    - Request body:
      ```json
      {"digests": [{"recipient": string, "period_seconds": integer, "first_due_in_seconds": number}]}
      ```
    - Side effect: wipes `emaildigest` and `sentemail`, then inserts the supplied digests. For each digest, set `last_sent_at = null` and `next_due_at = now + first_due_in_seconds`.
    - Response:
      ```json
      {"seeded": integer}
      ```
  - `POST /api/scheduler/start`
    - Request body: empty or `{}`.
    - Side effect: ensures the background scheduler loop is running. If a loop is already running, this must be a no-op (idempotent restart). Within 1 s of the call, `GET /api/scheduler/status` must report `running == true`.
    - Response:
      ```json
      {"running": true}
      ```
  - `POST /api/scheduler/stop`
    - Request body: empty or `{}`.
    - Side effect: signals the background loop to exit cleanly. Within 2 s, `GET /api/scheduler/status` must report `running == false`.
    - Response:
      ```json
      {"running": false}
      ```
  - `POST /api/scheduler/force_run`
    - Request body: empty or `{}`.
    - Side effect: invokes the same Force Run logic exposed in the UI, producing exactly one new `sentemail` row.
    - Response:
      ```json
      {"sent": 1, "digest_id": integer, "recipient": string}
      ```
  - `GET /api/scheduler/status`
    - Response shape:
      ```json
      {
        "running": boolean,
        "now": number,
        "due_count": integer,
        "queued_count": integer,
        "total_sent": integer
      }
      ```
    - Field semantics:
      - `running` is `true` while the background scheduler loop is alive.
      - `now` is the server-side unix timestamp in seconds at the moment of the request.
      - `due_count` is the number of `emaildigest` rows with `next_due_at <= now`.
      - `queued_count` is the number of `emaildigest` rows with `next_due_at > now`.
      - `total_sent` is the total number of rows in `sentemail`.
  - `GET /api/scheduler/sent`
    - Response shape:
      ```json
      {"rows": [{"id": integer, "digest_id": integer, "recipient": string, "sent_at": number}]}
      ```
    - Ordered by `sent_at` ascending.
- Behavioural requirements (verifier will exercise these via HTTP):
  - **Bounded throughput:** after seeding one digest with `period_seconds=2` and `first_due_in_seconds=0`, then starting the scheduler and waiting 6 s, the number of `sentemail` rows for that digest must be in the closed interval `[2, 4]`.
  - **No duplicate sends per tick:** in any single tick, the scheduler must not insert more than one `sentemail` row for the same digest. Equivalent observable rule: for any single digest, the time gap between consecutive `sent_at` values must be at least `period_seconds - 0.5`.
  - **Force Run is immediate:** after seeding one digest with `period_seconds=60` and `first_due_in_seconds=60` (so it is NOT due), calling `POST /api/scheduler/force_run` must produce exactly one new `sentemail` row whose `digest_id` matches that digest and whose `sent_at` is within ~2 s of `now` at call time. The scheduler must also reschedule the digest's `next_due_at` forward by `period_seconds` from the force-run moment.
  - **Idempotent restart:** calling `POST /api/scheduler/start` twice in a row must not spawn two concurrent loops. After two consecutive starts followed by `POST /api/scheduler/stop`, `GET /api/scheduler/status` must report `running == false` within 2 s.
  - **No ImmutableStateError:** the server log must not contain the substring `ImmutableStateError` after the verifier has exercised every endpoint.
- Source-code contract (verified by reading `.py` files under the project, excluding `.venv`, `node_modules`, `.web`, `__pycache__`):
  - At least one file contains the literal substring `@rx.event(background=True)`.
  - At least one file contains the literal substring `async with self`.
  - At least one file contains the literal substring `class EmailDigest` and `class SentEmail` (case-sensitive).
- Cleanup requirements:
  - The agent must terminate any background Reflex servers (for example with `pkill -f 'reflex run'`) before declaring the task complete. The verifier starts its own server and a leftover server bound to port 8000 will fail the test.

