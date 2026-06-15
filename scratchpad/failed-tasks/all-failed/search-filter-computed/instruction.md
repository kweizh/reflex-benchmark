# Reflex Searchable Product List with Cached Computed Vars

## Background
Reflex (https://reflex.dev) is a full-stack Python framework that compiles a Python state class into a synchronized React/Next.js frontend with a FastAPI backend. In this task you will build a small Reflex page that renders a searchable list of products. The implementation must showcase Reflex's `@rx.var(cache=True)` derived properties together with `rx.foreach` for dynamic rendering and `rx.input` for two-way state binding.

A scaffolded Reflex project is already present at `/home/user/myproject`. It was created with `uv init` and `uv add reflex`, and initialized using `uv run reflex init --template blank`. The default `myproject/myproject.py` only shows the boilerplate landing page. You must replace its content with a working searchable product list page.

## Requirements
- Define a hardcoded `products` list on the State class. It must be a `list[dict]` literal with **at least 10 entries**, where every entry contains at minimum the keys `name` and `category` (both strings).
- Add a synchronized `query: str = ""` state var that is bound to an `rx.input` element on the page (the input value must update `query` as the user types).
- Add a **cached** computed var `filtered_products` (decorated with `@rx.var(cache=True)`) that returns the entries of `products` whose `name.lower()` contains `query.lower()`. When `query` is empty, every product must be returned.
- Add a **cached** computed var `result_count` (decorated with `@rx.var(cache=True)`) whose implementation is exactly `return len(self.filtered_products)`.
- Render the filtered list with `rx.foreach`, displaying each item's `name` and `category` (both must be visible in the rendered output for each product).
- Render the result count using the text `Found {n} results` (e.g. `Found 7 results`), driven by `result_count`.
- The page must be reachable at the application root (`/`).

## Implementation Hints
- Reflex auto-discovers your app from `myproject/myproject.py`. Edit that file (and/or `myproject/state.py` if you prefer) to define the state and the page component, then register the page with `app.add_page(...)` at the project root path.
- `@rx.var` defaults to `cache=True`, but the verifier checks for an explicit `cache=True` keyword to ensure the caching contract is intentional.
- Bind the input to `query` using Reflex's two-way binding sugar (`value=State.query` + `on_change=State.set_query`) or `rx.input(on_change=State.set_query, value=State.query, ...)`. Reflex automatically generates the `set_query` event handler for you.
- Use `uv` for every Reflex command (e.g. `uv run reflex run`, `uv run reflex export`). System Python does **not** have Reflex installed.
- Reflex `run` starts a Next.js dev server on port 3000 (frontend) and a FastAPI backend on port 8000. The verifier will use both ports.
- If you start a background server during development, **always kill it before you finish** so the verifier can start its own clean server.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- Source file under test: `/home/user/myproject/myproject/myproject.py` (and any other files it imports from the project). The State class definition, both cached computed vars, and the page component **must** be reachable by importing this module via static AST analysis.
- Start command: `cd /home/user/myproject && uv run reflex run --loglevel info`
- Port: `3000` (frontend), `8000` (backend)
- AST requirements (verified by parsing the project source):
  - A subclass of `rx.State` (any class that inherits from `rx.State`) declares a class-level attribute `products` whose value is a list literal of at least 10 dict entries, each containing `name` and `category` string fields.
  - The same State class declares `query: str = ""`.
  - The State class defines two methods named `filtered_products` and `result_count` decorated with `@rx.var(cache=True)` (or `@reflex.var(cache=True)`).
  - The body of `result_count` contains the expression `len(self.filtered_products)`.
- Runtime requirements (verified after `uv run reflex run` is running):
  - `GET http://localhost:3000/` returns HTTP 200 and HTML that loads the Reflex app shell.
  - The compiled frontend bundle (anything fetched from `http://localhost:3000/_next/static/...`) contains references to the state field name `query` and the computed var name `filtered_products`, demonstrating the input binding and the foreach iteration are wired to state.
- After verification, **all background Reflex servers must be killed** by the executor; the verifier will also kill any lingering processes itself.

