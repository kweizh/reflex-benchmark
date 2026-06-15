# Wrap react-colorful as a Reflex NoSSR Component

## Background

Reflex lets you wrap any React component from npm into a native Reflex component by subclassing `NoSSRComponent` and declaring the npm `library`, the React `tag`, the available props as `rx.Var[...]`, and the event triggers as `rx.EventHandler[...]`. In this task you will wrap the [`react-colorful`](https://www.npmjs.com/package/react-colorful) library's `HexColorPicker` and use it on a Reflex page that previews the currently selected color.

You will be building a single Reflex application that demonstrates a real third-party React component being driven by Reflex state through a websocket round-trip. The frontend must mount the picker without server-side rendering, and the backend must receive the new color string on every change and store it on state.

## Requirements

- Implement a custom Reflex component class `ColorPicker(NoSSRComponent)` that wraps the `HexColorPicker` React component exported from `react-colorful` at version `5.7.0`.
  - The class must set `library = "react-colorful@5.7.0"` and `tag = "HexColorPicker"`.
  - It must expose a prop `color: rx.Var[str]`.
  - It must expose an event trigger `on_change: rx.EventHandler[lambda color: [color]]` that forwards the new color string from the React component.
- Expose a factory `color_picker = ColorPicker.create` that can be used as a normal Reflex component constructor.
- Define an `rx.State` subclass with:
  - A base var `color: str = "#ff0000"`.
  - An event handler `set_color(self, c: str)` that updates `self.color` to the value it receives.
- Build the index page (`/`) so that it renders:
  - A square preview built with `rx.box(width="80px", height="80px", background=State.color)` displayed ABOVE the picker.
  - The wrapped `color_picker(...)` instance, bound to the state color and wired so that its `on_change` triggers `State.set_color`.

## Implementation Hints

- Use the non-interactive setup from `plan.md`: `uv init`, `uv add reflex`, `uv run reflex init --template blank`. Manage Python with `uv`; do not rely on system Python for the Reflex app itself.
- Import `NoSSRComponent` from `reflex.components.component`.
- The `library` string includes the version pin so that the generated `package.json` references `react-colorful@5.7.0`.
- When building the frontend bundle Reflex will populate `.web/package.json` with the libraries declared on your wrapped components. You can produce this file with `uv run reflex export --frontend-only --no-zip` from the project root.
- The `on_change` handler must serialize its argument as `[color]` so that Reflex passes a single positional string to your Python event handler.
- Make sure to wire the picker's `color` prop to `State.color` and its `on_change` to `State.set_color` so the websocket round-trip actually updates state.
- After running any background `reflex run` or build, you are responsible for stopping all background servers so the verifier can run its own checks.

## Acceptance Criteria

- Project path: `/home/user/myproject`
- The Reflex application must live inside `/home/user/myproject` and be runnable with `uv run reflex run` from that directory.
- Start command (for verification of the running app): `uv run reflex run --env prod --backend-only`. The verifier will perform a frontend build separately with `uv run reflex export --frontend-only --no-zip`.
- The Python source must contain:
  - A class `ColorPicker` whose declared base class name is `NoSSRComponent`, where `NoSSRComponent` is imported from `reflex.components.component`.
  - On `ColorPicker`: a class attribute `library` whose string value starts with `react-colorful` and contains the substring `5.7.0`, and a class attribute `tag` equal to `"HexColorPicker"`.
  - On `ColorPicker`: an annotated attribute `color` of type `rx.Var[str]`.
  - On `ColorPicker`: an annotated attribute `on_change` of type `rx.EventHandler[...]` whose argument is a `lambda color: [color]` (single-argument lambda named `color` returning a list literal of `[color]`).
  - A module-level assignment `color_picker = ColorPicker.create`.
  - A state class inheriting from `rx.State` that declares `color: str = "#ff0000"` and an event handler method `set_color(self, c: str)` that assigns its parameter to `self.color`.
- After running `uv run reflex export --frontend-only --no-zip` inside the project directory, the file `/home/user/myproject/.web/package.json` must exist and its `dependencies` must include an entry whose key is exactly `react-colorful` (any version string is acceptable, but the dependency must be present).
- Background processes started during the task must be terminated before completion so that ports 3000 and 8000 are free for the verifier.

