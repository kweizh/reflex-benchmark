# Recursive Tree-View File Explorer (Reflex)

## Background
Build an interactive, recursive tree-view file explorer as a pure-Python web app using the [Reflex](https://reflex.dev) framework. The explorer renders a nested directory tree in which folders can be expanded and collapsed, files can be selected, and a breadcrumb shows the full path of the current selection.

The project must be managed with the `uv` package manager (some Reflex dependencies conflict with system Python packages).

## Requirements
- Create and run a Reflex app that serves a single page showing a directory tree.
- Model the tree with a custom, self-referential data type (a node has a name, a flag marking whether it is a directory, and a list of child nodes). Store the tree in application state.
- Render the tree so that every node is shown with visual indentation reflecting its depth. Nested children must be produced by iterating over reactive state (not a plain Python `for` loop over constants).
- Folders can be expanded/collapsed by clicking them. Expanded/collapsed status is tracked in state (e.g. a set/list of expanded node ids). When a folder is collapsed, none of its descendants are visible; when expanded, its direct children become visible.
- Files can be selected by clicking them. Selecting a file updates a breadcrumb that shows the full path from the root to the selected file.
- Display the total number of files (leaf, non-directory nodes) contained in the whole tree, derived reactively from the tree data.

## The tree to model
The app must contain exactly this directory structure (folders shown with a trailing `/`):

```
root/
  src/
    app.py
    utils/
      helpers.py
      math.py
  docs/
    guide.md
  README.md
```

There are 5 files in this tree: `app.py`, `helpers.py`, `math.py`, `guide.md`, and `README.md`.

## Implementation Hints
- Use a custom var type (an `rx.Base` subclass or a dataclass) whose `children` field is a list of the same type to represent nodes. Recursive rendering can be achieved by combining `rx.foreach` with a memoized component (`@rx.memo`) so a node component can render its own children.
- Use `rx.cond` to only render a node's children when that node is expanded, and to switch the breadcrumb between the empty and selected states.
- Use computed vars (`@rx.var`) for the total file count and for the selected breadcrumb path; use event handlers that take the clicked node's id/path as an argument to toggle expansion and to select files.
- Initialize the app with `uv`: create the project with `uv init`, add the dependency with `uv add reflex`, and initialize the Reflex project non-interactively with `uv run reflex init --template blank`. Run it with `uv run reflex run`.
- Project path: /home/user/tree_explorer
- Start command (run from the project path): `uv run reflex run`
- Frontend port: 3000 (backend runs on port 8000)

### Required, observable behavior (must match exactly)
- On first load, only the root folder is expanded. Its direct children `src`, `docs`, and `README.md` are visible, while deeper nodes (such as `app.py`, `utils`, `helpers.py`, `math.py`, `guide.md`) are NOT visible.
- Each folder label is rendered with its trailing name only (e.g. `src`, `utils`, `docs`, `root`); each file label shows its file name (e.g. `app.py`, `README.md`). Every visible node's clickable label text must exactly equal its name so nodes can be found by their text.
- Clicking a collapsed folder expands it (its direct children appear); clicking an expanded folder collapses it (all of its descendants disappear).
- Clicking a file selects it and updates a breadcrumb whose text is the full path from the root joined with ` / ` (space, slash, space). For example, selecting `helpers.py` shows `root / src / utils / helpers.py`; selecting `README.md` shows `root / README.md`; selecting `guide.md` shows `root / docs / guide.md`.
- Before any file is selected, the breadcrumb area shows the exact text `No file selected`.
- The page shows the total file count using the exact text `Total files: 5`.

### Cleanup
- After you finish and verify your work, you MUST stop/kill every background server or process you started (for example, any `reflex run` dev server or its frontend/backend processes) so that ports 3000 and 8000 are free. The grader will start the app itself.

