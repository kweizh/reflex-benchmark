# Multi-Step Registration Wizard with LocalStorage Persistence (Reflex)

## Background
Reflex is a full-stack Python framework that compiles declarative Python UI definitions into a Next.js/React frontend with a Python backend, synchronizing state over WebSockets. Reflex exposes a `rx.LocalStorage` helper that lets state vars persist in the browser's localStorage so values survive page refreshes.

Your task is to build a small registration wizard for a fictional service. The wizard collects user data across three steps. Because users sometimes accidentally refresh the page in the middle of filling out a long form, every draft field must be persisted to the browser's localStorage and restored automatically when the page loads again. On final submission the wizard clears all draft data.

## Requirements
- Build a Reflex application that exposes the wizard at the root route (`/`).
- The wizard has exactly three steps and the current step is tracked in a state variable named `step` (an `int` with default value `1`).
- The state must include the following draft fields, each declared with `rx.LocalStorage("", name="...")` so they are persisted in the browser's localStorage with explicit names:
  - `name`
  - `email`
  - `address`
  - `city`
  - `password`
  - `confirm_password`
- The state must include `submitted: bool = False` that is set to `True` only after a successful final submit.
- Provide event handlers `next_step` and `prev_step` that move `step` forward/backward but never outside the range `1..3`.
- Per-step validation:
  - Step 1 "Next" must only advance when both `name` and `email` are non-empty (after stripping whitespace) and `email` contains an `@`.
  - Step 2 "Next" must only advance when both `address` and `city` are non-empty.
  - Step 3 "Submit" must only succeed when both `password` and `confirm_password` are non-empty and `password == confirm_password`.
- On successful final submit the state must set `submitted = True` and clear all six LocalStorage draft vars (set them to empty strings).
- The frontend should render the field inputs for the active step. Each `rx.input` for a given field must use the field name as its `name=` attribute (so the rendered HTML includes `name="name"`, `name="email"`, `name="address"`, `name="city"`, `name="password"`, `name="confirm_password"`).
- After a successful submission, the page should clearly show a confirmation message containing the text `Registration complete` (bound to the `submitted` flag).

## Implementation Hints
- Use `uv` to manage the project. The provided environment already has `uv` installed and a `multistep_form` Reflex project scaffolded at `/home/user/myproject`.
- Review the Reflex docs on client storage to learn how `rx.LocalStorage(default, name=...)` works.
- All state vars must be JSON-serializable; the LocalStorage fields are typed as `str`.
- Use `rx.cond` (or `rx.match`) to switch between the three steps based on the value of `step`.
- Remember that any state mutation must happen inside an event handler method on the state class.
- When the final submission succeeds, clear each persisted field by assigning `""` to it in the same event handler that flips `submitted` to `True`.
- Always pass an explicit `name=` argument to every `rx.LocalStorage(...)` call so the browser localStorage keys are stable and predictable.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- Start command: `uv run reflex run --loglevel info` (run from `/home/user/myproject`).
- Frontend port: `3000` (Reflex frontend); backend port: `8000` (Reflex backend).
- The application home page (`/`) renders the wizard.
- The state class must define:
  - `step: int = 1`
  - `submitted: bool = False`
  - Six fields declared via `rx.LocalStorage("", name="<field>")` covering `name`, `email`, `address`, `city`, `password`, `confirm_password`.
- Event handlers `next_step` and `prev_step` must exist on the state class and must keep `step` within `1..3`.
- A handler must validate that `password == confirm_password` (and both non-empty) before setting `submitted = True`; the same handler must clear all six LocalStorage fields.
- The exported frontend (under `.web/`) must contain references to all six input field names: `name`, `email`, `address`, `city`, `password`, `confirm_password`.
- After the agent finishes the task, all background processes started by the agent (frontend dev server, backend, `reflex run`, etc.) must be terminated so that ports 3000 and 8000 are free.

