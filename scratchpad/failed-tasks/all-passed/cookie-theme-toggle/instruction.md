# Reflex App: Theme Toggle Persisted in a Cookie

## Background
Reflex is a full-stack Python framework for building web apps. Its [Client Storage](https://reflex.dev/docs/client-storage/overview/) APIs make it easy to persist small pieces of user state in the browser. In this task, build a tiny Reflex app whose state stores the user's preferred UI theme in an `rx.Cookie`, and renders a button that toggles between a light and a dark theme.

## Requirements
- A Reflex application initialized with `uv` in `/home/user/myproject`.
- A single state variable `theme` declared on a subclass of `rx.State` and backed by an `rx.Cookie` whose:
  - default value is the string `"light"`.
  - cookie name (sent to the browser) is `app_theme`.
- An event handler on the state that switches `theme` between exactly two values: `"light"` and `"dark"`. Clicking the button when the current value is `"light"` must set it to `"dark"`, and vice versa.
- A page at `/` containing:
  - An `rx.heading` above the button that renders the current theme in the form `Current: {State.theme}`.
  - An `rx.button` with the visible text `Toggle Theme` that, when clicked, triggers the toggle event handler.
- The Reflex frontend must be exportable in static form so that the compiled output references both the `Toggle Theme` label and the cookie-backed `theme` state.

## Implementation Hints
- Use the [non-interactive Reflex setup](https://reflex.dev/docs/getting-started/installation/) described in the project plan: `uv init`, `uv add reflex`, then `uv run reflex init --template blank`.
- The `rx.Cookie` constructor accepts both the default value and a `name` keyword argument for the cookie name on the client side. See the [Browser Storage API reference](https://reflex.dev/docs/api-reference/browser-storage/).
- Keep the toggle logic deterministic: never assign anything other than `"light"` or `"dark"` to `theme`.
- You do not need to actually theme the page styling — only the state value, heading text, and button matter.
- To validate the compiled frontend without a running dev server, the verifier runs `uv run reflex export --frontend-only --no-zip` inside the project. Make sure that command succeeds in your project layout.
- Do not leave any Reflex dev server running. Kill any background server processes before finishing.

## Acceptance Criteria
- Project path: /home/user/myproject
- The project is a valid Reflex application managed by `uv` (contains `pyproject.toml`, a `rxconfig.py`, and an app module created by `reflex init --template blank`).
- Static analysis of the project's Python source files must show:
  - An `rx.Cookie(...)` call used as the default value of a state field named `theme`, where the call includes both the default string `"light"` and the keyword argument `name="app_theme"`.
  - Exactly the two string literals `"light"` and `"dark"` referenced as the possible theme values in the toggle logic.
- Running `uv run reflex export --frontend-only --no-zip` from `/home/user/myproject` exits with status 0 and produces a `.web/` (or equivalent exported) directory.
- The exported frontend output contains:
  - The visible button label `Toggle Theme`.
  - A binding/reference to the `theme` cookie state (for example, the cookie name `app_theme` and/or the state variable `theme` appearing in the generated frontend artifacts).
- After verification, no Reflex backend or frontend dev server processes are left running on the machine.

