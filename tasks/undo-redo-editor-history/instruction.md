# Undo/Redo Text Editor with History Stacks (Reflex)

## Background
You are building a single-page text editor in pure Python with the **Reflex** framework. The editor keeps a full edit history so the user can undo and redo changes. The history must live entirely on the server as backend-only state (never synchronized to the browser), while the UI reactively reflects what can be undone/redone and how deep the history is.

A blank Reflex project has already been scaffolded and its dependencies installed with `uv` inside the project's virtual environment. You only need to implement the application logic and UI in the project's main app module.

## Requirements
- A single page served at `/` that lets the user edit a piece of text and navigate its history.
- Maintain two **backend-only** history stacks (an undo stack and a redo stack). These must NOT be sent to the client (i.e. they must be backend-only vars, not synchronized base vars).
- Committing a new value:
  - records the value that was current *before* the commit onto the undo stack,
  - sets the current content to the newly committed value,
  - clears the redo stack.
- Undo restores the most recently pushed value from the undo stack into the current content, and pushes the value that was current (before the undo) onto the redo stack.
- Redo does the inverse of undo: it re-applies the most recently undone value and pushes the pre-redo current value back onto the undo stack.
- The undo stack is bounded: it must retain at most **50** entries. When a commit would exceed 50 entries, the oldest entry is dropped so the depth never goes above 50.
- Expose reactive/computed indicators derived from the stacks: whether an undo is possible, whether a redo is possible, and a human-readable history-depth label.
- The Undo and Redo buttons must be disabled exactly when their action is not possible.

## Implementation Hints
- Model the current content as a synchronized state var, and the two history stacks as backend-only vars (underscore-prefixed) holding lists of string snapshots.
- Use event handlers for commit/undo/redo, computed vars (`@rx.var`) for the `can_undo`/`can_redo` booleans and the history-depth label, and `rx.cond` to drive the disabled state of the buttons.
- Enforce the 50-entry bound inside the commit handler itself.
- Project path: `/home/user/editor`
- The project's virtual environment and dependencies are already installed with `uv`; run every Reflex command through `uv run` from the project path (e.g. `uv run reflex run`).
- Start command (from the project path): `uv run reflex run`
- Frontend port: 3000 (backend runs on port 8000). The page under test is `http://localhost:3000/`.
- The page at `/` MUST expose these interface elements so behavior can be verified in a browser:
  - A single text input (textbox) used to enter the value to commit.
  - A button labeled `Commit` that commits the current input value as the new content.
  - A button labeled `Undo` and a button labeled `Redo`.
  - An element with HTML `id="content-display"` that shows the current committed content as its text.
  - An element with HTML `id="history-label"` whose text is EXACTLY `Undo depth: <u> | Redo depth: <r>`, where `<u>` is the current number of entries on the undo stack and `<r>` is the current number of entries on the redo stack (e.g. `Undo depth: 0 | Redo depth: 0`).
  - The `Undo` button must be disabled when the undo stack is empty; the `Redo` button must be disabled when the redo stack is empty.
- The initial current content is the empty string, with both stacks empty (so both buttons start disabled and the history label reads `Undo depth: 0 | Redo depth: 0`).
- IMPORTANT: If you start the Reflex dev server (or any other background process) to try out your work, you MUST stop/kill all such background servers before finishing so that ports 3000 and 8000 are free. The verification step starts its own server.

