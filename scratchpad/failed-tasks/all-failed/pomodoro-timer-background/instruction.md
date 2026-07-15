# Pomodoro Timer with a Background Tick Loop (Reflex)

## Background
Build a full-stack Pomodoro timer web app in pure Python using the Reflex framework. A background task drives a one-second tick loop that counts down the remaining time, automatically alternates between Work and Break phases, tracks completed focus sessions, and logs every completed work session to a local SQLite database.

## Requirements
- Build a countdown timer that alternates between two phases:
  - The **Work** phase lasts **5 seconds**.
  - The **Break** phase lasts **3 seconds**.
- The app starts in the Work phase, with the full work time remaining, and **not** running.
- While the timer is running, a background task decrements the remaining time by one every second.
- When the remaining time reaches `00:00`:
  - If the phase that just finished was **Work**: increment the completed-sessions counter, insert a row into the SQLite log, then switch to the **Break** phase with the break time remaining.
  - If the phase that just finished was **Break**: switch back to the **Work** phase with the work time remaining.
  - The timer keeps running automatically across phase changes until it is paused.
- Controls:
  - **Start** begins or resumes the countdown.
  - **Pause** stops the countdown but keeps the current phase and the current remaining time.
  - **Reset** stops the countdown, returns to the Work phase, and restores the full work time.
- Persist a record of every completed **Work** session in a local SQLite database.
- Show live statistics for the current day that are derived from the database.

## Implementation Hints
- Use a Reflex background task (`@rx.event(background=True)`) for the tick loop, and mutate state only inside an `async with self` block; sleep about one second between ticks.
- Track whether the timer is running with a backend-only (underscore-prefixed) variable so the running flag is never synchronized to the client; the frontend should only send Start/Pause/Reset events.
- Guard the tick loop so that pressing Start repeatedly never spawns more than one concurrent countdown (the timer must never tick faster than once per real second).
- Define the log table as an `rx.Model` (`table=True`) and create the SQLite schema with Reflex's database migration commands; write rows with `rx.session()`.
- Use cached computed vars to format the remaining time as `MM:SS` and to derive today's statistics from the database.

### Hard requirements / interface
- Project path: `/home/user/pomodoro_timer`
- Manage the Python environment with `uv` (the app depends on `reflex`). Initialize the app non-interactively (for example, using the `blank` template).
- Start command (run from the project path): `uv run reflex run`
- Frontend port: `3000`. Backend port: `8000`.
- While running, the timer must tick down exactly one second per real second.
- On the page served at `/`, render all of the following visible text, bound to state vars:
  - The current phase as `Phase: Work` or `Phase: Break`.
  - The remaining time formatted as zero-padded `MM:SS` (for example, `00:05`).
  - The count of completed work sessions in this run as `Completed: <n>` (starts at `0`).
  - The number of work sessions logged today (read from the database) as `Today: <n>` (starts at `0`).
- Provide three buttons labeled exactly `Start`, `Pause`, and `Reset`.
- Log each completed Work session as one row in a SQLite table named `pomodoro_session` that has at least the columns `phase` (text, value `work`), `duration_seconds` (integer, value `5`), and `completed_at` (ISO 8601 text timestamp). Use the app's default SQLite database file `reflex.db`, located in the project path.
- After you finish building and validating the app, stop/kill any Reflex dev server or other background processes you started, so that nothing is left listening on ports 3000 or 8000.

