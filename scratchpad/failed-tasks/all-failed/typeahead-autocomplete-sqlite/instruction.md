# Typeahead Autocomplete Search over SQLite (Reflex)

## Background
Build a full-stack **Reflex** (pure-Python web framework) app that provides a **typeahead / autocomplete** search box over a product catalog stored in SQLite. As the user types, a debounced handler runs an asynchronous `LIKE` query against the database and shows a ranked dropdown of suggestions. Clicking a suggestion fills the input and reveals that product's detail. This is an autocomplete dropdown experience (suggestions appear/disappear as you type and are chosen), NOT a static filtered table.

## Requirements
- A single-page Reflex app with a search input and a suggestion dropdown.
- Typing into the box is **debounced** (via the input's `on_change`), and the handler queries SQLite **asynchronously** using `rx.asession` inside a background event handler.
- Matching is a case-insensitive substring (`LIKE`) match on the product **name**.
- The dropdown is rendered with `rx.foreach` over the ranked suggestions.
- Use `rx.cond` to distinguish three states: an empty-query prompt, a no-results message, and the results list.
- A cached **computed var** produces a result-count label string.
- Selecting a suggestion (an event handler that takes the product id as an argument) fills the input with the chosen name and displays the selected product's detail (category, price, description).
- The catalog is seeded from the provided dataset (see hints).

## Implementation Hints
- Project path: `/home/user/catalog_app` (initialize the Reflex app here with app name `catalog_app`).
- Manage the Python environment with **uv** (e.g. `uv init`, `uv add reflex`, `uv run reflex init --template blank`). Install `aiosqlite` as a dependency and set `async_db_url="sqlite+aiosqlite:///reflex.db"` (pointing at the same SQLite file as `db_url`) in `rxconfig.py`, otherwise `rx.asession` will not work.
- A seed dataset is provided at `/home/user/catalog_app/products.csv` with the header `name,category,price,description`. On app startup, if the product table is empty, import **all** rows from this CSV into the database (store `price` as a number). Keep the database and the API in sync (same DB file).
- Expose a small JSON HTTP API on the backend using the Reflex `api_transformer` (a FastAPI instance). The autocomplete UI event handler and these API routes MUST use the exact same query + ranking logic:
  - `GET /api/suggest?q=<query>` returns a JSON object with exactly the keys `query`, `count`, `label`, `results`.
    - `query`: the input query with surrounding whitespace stripped.
    - `results`: a JSON array (max length 8) of product objects, each with exactly the keys `id`, `name`, `category`, `price`, `description`.
    - `count`: the number of objects in `results` (an integer, so at most 8).
    - Ranking / matching rules for `results`: include products whose lowercased `name` contains the lowercased, stripped query. Order them so that names whose lowercased value **starts with** the query come first (prefix group), followed by names that contain the query elsewhere (substring group). Within each group, sort ascending case-insensitively by name, breaking ties by ascending `id`. Then truncate to the first 8.
    - `label`: if the stripped query is empty, `"Start typing to search the catalog"`; else if there are zero matches, `"No matches found"`; otherwise `"{count} results"` (e.g. `"6 results"`).
    - An empty or whitespace-only query yields `count` 0, `results` `[]`, and the empty-query prompt label.
  - `GET /api/detail?id=<id>` returns the single product JSON object (keys `id`, `name`, `category`, `price`, `description`) for that id, or HTTP status 404 if no product has that id.
- The UI's computed-var label MUST use the same text as the API `label`. The empty-query prompt shown on initial page load MUST be exactly `"Start typing to search the catalog"`.
- The page MUST contain a heading with the exact text `Catalog Search`, and the search input MUST have the placeholder `Search products...`.
- Start command (run from inside the project): `uv run reflex run`. This serves the frontend on port `3000` and the backend on port `8000`. The backend health route `http://localhost:8000/ping` returns `"pong"`.
- After you finish building and validating, you MUST stop/kill every background server or process you started (frontend and backend) so no server is left running when you are done.

