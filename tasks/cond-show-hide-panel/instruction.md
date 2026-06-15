# Reflex Conditional Panel with Switch and Cached Visibility Label

## Background
Build a small Reflex application that demonstrates the most common conditional-rendering pattern: a switch (or button) toggles a boolean piece of state, and the UI conditionally renders a panel via `rx.cond`. A cached computed var derives a human-readable label from the same boolean so the visibility status is always in sync with the rendered panel.

## Requirements
- A Reflex project at `/home/user/myproject` initialized with the blank template using `uv` and `reflex`.
- The index page `/` exposes:
  - A control bound to a boolean state var `show_panel` (default `False`) via `on_change`. `rx.switch` is the recommended control, but a button that toggles the same state var is also acceptable.
  - A `rx.cond` block that renders a panel containing the literal text `Secret Panel Content` when `show_panel` is true, and renders nothing (or an empty placeholder) when it is false.
  - A status label that reads exactly `Visibility: shown` when the panel is shown and `Visibility: hidden` when it is hidden. The label text must come from a cached computed var named `visibility_label`.

## Implementation Hints
- Use `uv` to manage the Python environment and initialize the Reflex app non-interactively (`uv init`, `uv add reflex`, `uv run reflex init --template blank`).
- Refer to the Reflex docs for [Conditional Rendering](https://reflex.dev/docs/components/conditional-rendering/), the [Switch component](https://reflex.dev/docs/library/forms/switch/), and [Computed Vars](https://reflex.dev/docs/vars/computed-vars/). Do not assume APIs you have not verified.
- `rx.switch` emits a boolean through its `on_change` trigger; bind it to a setter that updates `show_panel`.
- Mark the computed var explicitly as cached (`@rx.var(cache=True)`) and have it return a `str`.
- Stop any long-running development servers (e.g. `uv run reflex run`) that you started for manual testing before finishing the task. The verifier compiles the frontend with `uv run reflex export --frontend-only --no-zip` and inspects the source code; it does not require a running server.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- Start command: `uv run reflex run --env prod`
- Port: `3000`
- Routes:
  - `/`: renders the toggle control, the conditional panel, and the visibility label.
- A boolean state var named `show_panel` exists and defaults to `False`.
- A cached computed var named `visibility_label` exists on the same state class and returns `Visibility: shown` when `show_panel` is true and `Visibility: hidden` otherwise.
- The `/` page uses `rx.cond` referencing the state's `show_panel` to conditionally render the panel containing the literal `Secret Panel Content`.
- After running `uv run reflex export --frontend-only --no-zip` in the project directory, the compiled frontend output (the generated `.web/` directory or any zipped artifact) contains all three literals: `Secret Panel Content`, `Visibility: shown`, and `Visibility: hidden`.
- No external environment variables are required to run the app or the tests.
- Background servers: stop any dev server you started before submitting; the verifier compiles the frontend itself and does not rely on a running app.

