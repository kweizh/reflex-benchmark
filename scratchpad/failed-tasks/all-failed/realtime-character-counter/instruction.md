# Real-Time Character & Word Counter (Reflex)

## Background
Reflex is a full-stack Python framework for building reactive web apps. In this task you will build a small reactive page using Reflex that demonstrates a `rx.text_area` bound to a State var, plus two derived counters implemented as cached computed vars.

## Requirements
- Build a single-page Reflex app that renders at the index route `/`.
- The page MUST contain:
  - A `rx.text_area` component with `id="content_input"` that is bound to a State var named `content`. The textarea must update `content` as the user types.
  - A `rx.text` component that displays the character count of `content` in the format `Characters: N` (no leading zeros, plain integer).
  - A `rx.text` component that displays the word count of `content` (whitespace-separated tokens) in the format `Words: M`.
- Both counters MUST be implemented as **cached computed vars** on the State class (`@rx.var(cache=True)` or `@rx.var`), not as inline expressions or event handlers.
- Use `uv` to manage the project's Python environment.

## Implementation Hints
- Bootstrap the project non-interactively with `uv init`, `uv add reflex`, then `uv run reflex init --template blank`.
- Define a `State` class that holds `content: str = ""` and decorate the two count methods with `@rx.var`.
- Hook the text area to `State.content` by using `value=State.content` together with `on_change=State.set_content` (Reflex auto-generates `set_content`), or by defining your own event handler.
- Run the app with `uv run reflex run` (or `--backend-only` if you only want the websocket backend) for local testing.
- Verify locally that visiting http://localhost:3000/ shows your textarea and the two counter lines.
- After verification, **kill all background reflex processes** so the evaluation environment is clean.

## Acceptance Criteria
- Project path: /home/user/myproject
- Start command: `uv run reflex run`
- Frontend port: 3000
- Backend port: 8000
- Routes:
  - `GET /`: Returns HTTP 200 and renders the page containing the text area `#content_input` and the two text lines.
- The Reflex project structure must be valid: `rxconfig.py` exists at the project root and defines a Reflex app, and the app module imports `reflex as rx`.
- The main app source code MUST define two `@rx.var`-decorated methods on a State subclass:
  - One whose body counts characters of `content` (e.g. via `len(self.content)`).
  - One whose body counts whitespace-separated words of `content` (e.g. via `len(self.content.split())`).
- The `rx.text_area` component must use `id="content_input"`.
- All background dev servers started during the task MUST be stopped before the task is considered complete.

