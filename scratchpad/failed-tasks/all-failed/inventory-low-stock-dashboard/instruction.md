# Inventory Low-Stock Dashboard (Reflex + SQLite)

## Background
Build a full-stack inventory management dashboard entirely in Python using the [Reflex](https://reflex.dev/docs/getting-started/introduction/) framework. The app tracks products and their stock levels in a local SQLite database (via `rx.Model`), lets operators adjust stock, and surfaces aggregate inventory analytics (total value, low-stock count, and a filtered low-stock list). A background task periodically refreshes the aggregate snapshot so the UI stays current.

Everything runs locally: a local SQLite database file plus the Reflex dev server (frontend on port 3000, backend on port 8000). No external services, cloud deployment, or network APIs are involved.

## Requirements
- Create a Reflex project and define a `Product` database model (`rx.Model`, `table=True`) persisted in the built-in SQLite database. Each product has: `name` (str), `sku` (str, unique business key), `quantity` (int), `price` (float, unit price), and `reorder_threshold` (int).
- On startup, if the products table is empty, seed it with exactly these five products:
  | name | sku | quantity | price | reorder_threshold |
  | --- | --- | --- | --- | --- |
  | Aluminum Bolt M6 | BOLT-M6 | 8 | 0.25 | 20 |
  | Steel Hinge | HINGE-ST | 50 | 3.50 | 15 |
  | Copper Wire 10m | WIRE-CU10 | 5 | 12.00 | 10 |
  | Plastic Grommet | GROM-PL | 200 | 0.10 | 100 |
  | Rubber Gasket | GASK-RB | 12 | 1.75 | 12 |
- Build a dashboard page that lists all products in a table using `rx.foreach` over a state var. A product is "low stock" when `quantity < reorder_threshold`; use `rx.cond` to visually highlight low-stock rows.
- Expose three aggregate values as computed vars (`@rx.var`) derived from the current product list:
  - `total_inventory_value`: sum of `quantity * price` across all products (a float).
  - `low_stock_count`: number of products where `quantity < reorder_threshold`.
  - `low_stock_products`: the filtered list of low-stock products.
- Implement a stock-adjustment event handler that changes a product's `quantity` by an integer delta inside a SQLite transaction (`rx.session`). The resulting quantity must never be negative: the persisted value is `max(0, current_quantity + delta)`.
- Add a background task (`@rx.event(background=True)`) that periodically (about every 2 seconds) recomputes the aggregate snapshot from the database and stores it on the state, mutating state only inside an `async with self` block.
- Additionally expose a small JSON HTTP API on the Reflex backend (port 8000) by passing a FastAPI instance as the app's `api_transformer`. All endpoints read/write the SAME SQLite database used by the UI.

## Implementation Hints
- Use `uv` for all Python environment and dependency management. Initialize the project non-interactively, e.g. `uv init`, `uv add reflex`, `uv run reflex init --template blank`, then create the schema with `uv run reflex db init`, `uv run reflex db makemigrations --message "initial schema"`, and `uv run reflex db migrate`. Note: a model is only picked up by migrations once it is imported/used in the app.
- Reflex marks the background-task state proxy immutable outside `async with self`; keep DB reads inside the block or refresh state within it.
- Consider sharing a single helper that computes the stats and a single helper that adjusts stock, so the UI state (computed vars / event handler) and the JSON API stay consistent.
- The low-stock rule is strict: `quantity < reorder_threshold` (equal quantity is NOT low stock).
- Project path: /home/user/inventory_app
- The SQLite database file must be the project's default database at /home/user/inventory_app/reflex.db, with the products stored in a table named `product`.
- Start command (run from the project directory): `uv run reflex run` (frontend on port 3000, backend on port 8000).
- After you finish building and any manual verification, you MUST stop/kill every background server or process you started (Reflex dev server, frontend, backend) so no server is left listening on ports 3000 or 8000.
- HTTP JSON API (served on the backend, http://localhost:8000):
  - `GET /api/products`: returns status 200 and a JSON array of all products ordered by `sku` ascending. Each object has exactly the keys `name`, `sku`, `quantity`, `price`, `reorder_threshold`.

    ```json
    // Response
    [
      { "name": string, "sku": string, "quantity": number, "price": number, "reorder_threshold": number }
    ]
    ```

  - `GET /api/stats`: returns status 200 and the aggregate stats object.

    ```json
    // Response
    {
      "total_inventory_value": number,
      "low_stock_count": number,
      "low_stock_products": [
        { "name": string, "sku": string, "quantity": number, "reorder_threshold": number }
      ]
    }
    ```
    The `low_stock_products` array contains only products with `quantity < reorder_threshold`, ordered by `sku` ascending.

  - `POST /api/adjust`: accepts a JSON body and adjusts one product's stock in a SQLite transaction, clamping the stored quantity to a minimum of 0. Returns 200 with the updated product, or 404 if the `sku` does not exist.

    ```json
    // Request
    { "sku": string, "delta": number }
    ```
    ```json
    // Response (200)
    { "name": string, "sku": string, "quantity": number, "price": number, "reorder_threshold": number }
    ```
- Browser-checkable: navigating to http://localhost:3000 shows the dashboard page containing the heading text `Inventory Dashboard`.

