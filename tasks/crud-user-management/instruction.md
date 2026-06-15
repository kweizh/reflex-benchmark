# CRUD User Management with Reflex

## Background
Build a simple full-stack CRUD application using the [Reflex](https://reflex.dev) framework. The application manages a list of users stored in the built-in SQLite database via Reflex's `rx.Model` and `rx.session` synchronous ORM helpers.

## Requirements
- Define a `User` model that subclasses `rx.Model` with `table=True` and has the fields `username: str`, `email: str`, and `is_active: bool = True`.
- Provide a single page at `/` that contains:
  - A form for creating a new user with `username` and `email` inputs and a `Create` button.
  - A table listing all existing users (showing at least `username`, `email`, and `is_active`).
  - A `Delete` button and a `Toggle` button on each row to remove the user or toggle their `is_active` flag.
- Persist all changes synchronously using `with rx.session() as session: ...` blocks (do not use `rx.asession`).
- After creating, deleting, or toggling a user, the visible user list must reflect the change without requiring a manual page reload.
- The application must be launched with `uv run reflex run` and the user-facing page served on port `3000`.

## Implementation Hints
- Use `uv` to bootstrap the project (`uv init`, `uv add reflex`) and `uv run reflex init --template blank` to create the app skeleton non-interactively.
- Run `uv run reflex db init`, `uv run reflex db makemigrations --message init`, and `uv run reflex db migrate` to create the SQLite `reflex.db` file with the `user` table.
- Define `User` once and reuse it inside the State class for the `users: list[User]` base var.
- Implement three event handlers on the state: `create_user`, `delete_user(user_id)`, and `toggle_active(user_id)`; also expose a `load_users` event for refreshing the table.
- Inside delete, use `session.delete(user); session.commit()` after querying for the user by id; for toggle, mutate `is_active` and `session.add` + `session.commit()`.
- Wire `load_users` to run on page mount (e.g., via `on_mount` of the page) so the table is populated when the user visits `/`.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- Start command: `uv run reflex run --loglevel info`
- Port: `3000` (frontend)
- A SQLite database file `reflex.db` exists at `/home/user/myproject/reflex.db` after running the `reflex db ...` migration commands, and contains a `user` table with the columns `id` (integer primary key), `username` (text), `email` (text), and `is_active` (boolean/integer).
- The `User` model is declared as `class User(rx.Model, table=True)` with fields `username: str`, `email: str`, and `is_active: bool = True`.
- The Reflex State class exposes a `users: list[User]` base var and a `load_users` event handler.
- The state defines three additional event handlers named `create_user`, `delete_user`, and `toggle_active`. `delete_user` and `toggle_active` accept a `user_id` argument.
- At least two distinct `with rx.session()` blocks exist in the application source for the create operation and the delete or toggle operation.
- The exported frontend (the output of `uv run reflex export --frontend-only --no-zip`) contains the literal labels `Create`, `Delete`, and `Toggle` somewhere under `/home/user/myproject/.web` (e.g., inside the generated `_next` pages).
- After starting the application with the start command above, navigating to `http://localhost:3000/` renders the create form and the user table.
- Kill any background dev server (`uv run reflex run`) processes started during development before finishing the task.

