# Optimistic Todo List with Rollback (Reflex)

## Background
Build a single-page todo application with **Reflex** (a pure-Python full-stack web framework). The app must use an *optimistic UI* pattern: when the user adds, toggles, or deletes a todo, the change is shown in the UI immediately, and only afterwards is it saved to a local SQLite database. If the save fails, the optimistic change is rolled back and an error banner is shown.

To make failures deterministic (no external services involved), the persistence step is *simulated locally*: a save is considered to have FAILED whenever the todo's title contains the substring `fail` (case-insensitive). Every other save succeeds and is written to SQLite.

## Requirements
- A user can add a todo by typing a title and submitting it.
- A user can toggle a todo between active and completed.
- A user can delete a todo.
- Each of these three actions must update the visible list **immediately** (optimistically), then perform a short simulated asynchronous persistence step against SQLite.
  - If the affected title contains `fail` (case-insensitive), the persistence step fails: the optimistic change must be rolled back so the list returns to its previous contents, and an error banner must be displayed naming the offending title.
  - Otherwise the change is committed to SQLite and the error banner is cleared.
- On page load, the app must load and display the todos currently stored in SQLite (so successful changes survive a page reload and rolled-back changes never appear).
- Show live counts of the todos.

## Implementation Hints
- Project path: `/home/user/optimistic_todo`
- Manage the Python environment with `uv` (create the venv, add `reflex`, and run everything through `uv run ...`). Initialize the app non-interactively with the blank template, and set up the SQLite schema with the Reflex database CLI before running.
- Implement each mutating action as a **generator event handler** that `yield`s the optimistic state to the client first, then performs the simulated async persistence and either commits or rolls back.
- Track in-flight/pending operations using **backend-only state variables** (names prefixed with `_`), and expose the three counts using **computed vars** (`@rx.var`).
- Persist todos with SQLite through Reflex's database layer (`rx.session` or `rx.asession`). Use the default database (`reflex.db` in the project root).
- The simulated persistence step must introduce only a brief delay (well under one second) so the optimistic update is observable but the app stays responsive.

### Hard requirements (the app is checked against these exact facts)
- Start command: `uv run reflex run` — the frontend must serve on port **3000** and the backend on port **8000**. The app UI is at `http://localhost:3000`.
- Persist todos in a SQLite table named `todoitem` containing at least the columns `id`, `title`, and `completed` (a truthy/`1` value means completed). Use the default database file `reflex.db` in the project root.
- The main page must contain:
  - A text input whose placeholder is exactly `New todo`.
  - A button whose visible label is exactly `Add` that submits the value currently in that input.
  - One element per todo, each carrying the attribute `data-testid="todo-item"`, displaying the todo's title text, containing a checkbox (an `<input type="checkbox">`) that toggles its completed state, and containing a button whose visible label is exactly `Delete` that deletes that todo.
  - Three count readouts rendered as the exact text `Active: N`, `Completed: N`, and `Total: N` (where `N` is the current integer count). `Active` counts not-completed todos, `Completed` counts completed todos, and `Total` is all todos.
  - An error element carrying the attribute `data-testid="error-banner"` that is present (and contains the offending title text) only after a save fails, and is absent or empty when the most recent action succeeded or when no action has failed yet.
- The failure rule is: a title containing the substring `fail` (case-insensitive) must never be written to SQLite; the optimistic change for it must be rolled back so it does not remain in the list.
- After you finish building and verifying, **kill every background server you started** (for example any `uv run reflex run` process). Do not leave any process listening on ports 3000 or 8000.

