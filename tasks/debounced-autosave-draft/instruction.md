# Note Editor with Debounced Autosave (Reflex)

## Background
Reflex is a pure-Python full-stack web framework. Build a single-page **note editor** that autosaves the draft to a local SQLite database after the user stops typing, without any manual "Save" button. The editor must show a live save-status indicator and restore the most recently saved draft whenever the page is loaded.

A blank Reflex project managed by `uv` already exists at the project path (created with `uv init`, `uv add reflex`, and `uv run reflex init --template blank`). Implement the feature inside that project. Because some Reflex dependencies conflict with system Python packages, you MUST run every Reflex command through `uv` (e.g. `uv run reflex ...`).

## Requirements
- The index page (`/`) renders a multi-line text area for the note body plus a visible save-status indicator.
- Typing into the text area is **debounced**: the backend receives the new content only after the user pauses, not on every keystroke.
- A short **quiet period** after the last change, a **background task** persists the current draft to SQLite and then updates the status indicator. Autosave must be fully automatic (no button, no form submit).
- Persist the note in a SQLite-backed Reflex database model named `Draft` that has at least a `content` text column. There is a single logical draft (the app always saves/restores the same note).
- When the page loads, the app must **restore** the most recently saved draft from SQLite so the text area shows the previously saved content.
- Track "dirty" (unsaved-changes) state using a **backend-only** state var, and derive the status label with a **computed var**.

## Implementation Hints
- Project path: `/home/user/note_app` (implement the app inside the existing `note_app` package/module).
- Wrap the text area so its `on_change` is debounced (Reflex's debounced input supports a `debounce_timeout`). Keep the text area's value bound to a base state var.
- Use a background event handler (`@rx.event(background=True)`) for the save. Remember that a background task may only mutate state inside an `async with self:` block, and should sleep for the quiet period outside the lock. Guard against redundant concurrent saves.
- Persist with a Reflex database model (`rx.Model`, `table=True`) using `rx.session()`/`rx.asession()`. Set up the database schema so the table exists on a fresh start (e.g. `uv run reflex db init`, `uv run reflex db makemigrations`, `uv run reflex db migrate`). The database file is `/home/user/note_app/reflex.db` (default `sqlite:///reflex.db`).
- Restore the saved draft using a page **on_load** event handler.
- Mark unsaved edits with a backend-only var (a name starting with `_`) and expose the status text through a computed var (`@rx.var`).
- The status indicator must display exactly these labels for the three states:
  - `Unsaved` — there are edits that have not been saved yet (and the initial state before anything is saved).
  - `Saving...` — a save is currently in progress.
  - `Saved` — after a successful save; the text must start with the word `Saved` and also include a timestamp of when the save happened (e.g. `Saved at 14:03:22`).
- Start command (run from the project path): `uv run reflex run`. This serves the frontend on port `3000` and the backend on port `8000`.
- Route: the editor lives at `/` (open `http://localhost:3000/`).
- After you finish, **stop every Reflex dev server and background process you started** (kill the `reflex run` process) so that nothing is left listening on ports 3000 or 8000.

