# Dynamic Tab-Based Match Panel with Reflex

## Background
Reflex is a full-stack Python web framework that compiles declarative Python UI definitions into a Next.js/React frontend and a FastAPI backend. The `rx.match` primitive lets you render different components based on the value of a state variable, similar to a switch/case pattern.

Your task is to build a small single-page Reflex application that demonstrates a tab-based UI where the visible panel switches based on the active tab. You must implement this using `rx.match` (not `rx.cond`).

## Requirements
- Initialize a Reflex project at `/home/user/myproject` using `uv` for Python environment management.
- The application must expose a single page at the index route `/`.
- The page must render three tabs as `rx.button` components, labelled exactly `Profile`, `Settings`, and `About`.
- A State subclass must hold a string variable `active_tab` that defaults to the value `"profile"`.
- Clicking a tab button must update `active_tab` to the lowercase form of the tab label (`"profile"`, `"settings"`, or `"about"`).
- Below the tab buttons, use `rx.match(State.active_tab, ...)` with at least three explicit case branches plus an explicit default branch to display the corresponding text:
  - case `"profile"` -> `rx.text("User Profile Page")`
  - case `"settings"` -> `rx.text("Settings Page")`
  - case `"about"` -> `rx.text("About Page")`
  - default -> `rx.text("Unknown Tab")`

## Implementation Hints
- Use `uv init`, `uv add reflex`, and `uv run reflex init --template blank` to scaffold the project in a non-interactive way.
- Define the state by subclassing `rx.State` and declaring `active_tab: str = "profile"`.
- Use `rx.button("Profile", on_click=...)` etc. Bind each button's `on_click` to an event handler (or a single parameterized event handler) that mutates `active_tab` to the lowercased label.
- Recall that `rx.match` requires tuples for each case and a single non-tuple default value as the last argument.
- The default Reflex blank template usually defines the main page via the `index` function registered with `app.add_page`. Modify it to include the tabs and the match-based panel.
- After you finish implementing, you can verify the rendered output by running `uv run reflex export --frontend-only --no-zip`, which compiles the static frontend bundle into the `.web/_static` directory.
- IMPORTANT: If you start any background process such as `uv run reflex run`, you MUST terminate it before finishing the task (e.g., `pkill -f 'reflex run' || true`). Do not leave any Reflex dev/backend processes alive.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- The project is a valid Reflex project managed by `uv` (a `pyproject.toml` and a `rxconfig.py` exist at the project root).
- The Reflex application has a single page registered at the index route `/`.
- The page source contains exactly three `rx.button(...)` elements with the literal labels `Profile`, `Settings`, `About`.
- A `rx.State` subclass defines a string field `active_tab` with the default value `"profile"`.
- The source code uses `rx.match(...)` referencing `active_tab` with three explicit case tuples for `"profile"`, `"settings"`, `"about"` (in any order) plus a default branch.
- Each tab button's `on_click` handler sets `active_tab` to the lowercased tab label.
- Running `uv run reflex export --frontend-only --no-zip` from the project root succeeds and produces a compiled frontend bundle under `.web/_static` that contains the literal strings `User Profile Page`, `Settings Page`, `About Page`, and `Unknown Tab`.
- No Reflex background server processes are left running at the end of the task.

