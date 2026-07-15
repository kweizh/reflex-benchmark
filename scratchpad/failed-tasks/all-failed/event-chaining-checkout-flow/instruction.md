# Reflex Checkout Flow with Chained Event Handlers

## Background
You are working in a pre-initialized Reflex (pure-Python full-stack framework) project located at `/home/user/checkout_app`. The project was created with the blank template and its Python environment is managed by `uv` (Reflex and its dependencies are already installed, the SQLite database is already initialized, and the frontend was already set up so the app can run offline). Your job is to implement a small e-commerce **checkout pipeline** that showcases Reflex event chaining, generator-based UI updates, a transactional SQLite reservation, and a computed var that reports the current pipeline step.

A single "Place Order" action must run a sequence of chained event handlers that validate the cart, reserve stock, and confirm the order. Each stage must `yield` an intermediate UI status update before handing control to the next stage, and stock reservation must be transactional: if any line item cannot be satisfied, the whole reservation is rolled back so that no stock is deducted and no order is recorded.

## Requirements
- Implement everything inside the existing app module `/home/user/checkout_app/checkout_app/checkout_app.py`.
- Define a SQLite-backed model `Product` (a `rx.Model` table) with at least the fields `name: str`, `stock: int`, and `price: float`.
- Define a SQLite-backed model `Order` (a `rx.Model` table) with at least the fields `product_name: str`, `quantity: int`, and `status: str`.
- Define a state class named `CheckoutState` that holds:
  - a base var `cart: dict[str, int]` mapping a product name to the requested quantity,
  - a base var `status_message: str` that reflects the latest pipeline status,
  - a computed var `current_step: str` that reports the current pipeline stage.
- Implement a `place_order` event handler that starts a chain of separate event handlers: cart validation, stock reservation, then order confirmation. Chaining MUST be done by returning/yielding the next event handler (not by inlining all logic into one function). On any failure the chain must divert to an error/failure handler instead of continuing.
- Each successful stage must `yield` at least one intermediate UI update so the frontend observes the status changing over the course of a single "Place Order" click.
- Stock reservation must run as a single SQLite transaction across all cart line items: deduct `stock` for every item, and if any item has insufficient stock, roll back the entire transaction (no partial deductions) and do not create any `Order` rows.
- On success, deduct the reserved quantities from `Product.stock` (committed) and insert one `Order` row per cart line item with `status` set to `"confirmed"`.
- Build a minimal index page that shows a heading containing the text `Checkout`, renders the current `status_message`, uses conditional rendering (e.g. `rx.cond` / `rx.match`) to display the pipeline status, and has a button labeled `Place Order` wired to `CheckoutState.place_order`.

## Implementation Hints
- Project path: `/home/user/checkout_app`
- App module to edit: `/home/user/checkout_app/checkout_app/checkout_app.py`
- Use the Reflex event system: an event handler can `yield` to push an intermediate `StateUpdate`, and can chain to another handler by returning or yielding the handler itself (reference it via the state class, e.g. `CheckoutState.reserve_stock`).
- Use `rx.session()` for the database work and rely on its transaction semantics (nothing is persisted unless `session.commit()` is called, and `session.rollback()` abandons pending changes) so the reservation is all-or-nothing.
- If you add or change table schemas, apply migrations with `uv run reflex db makemigrations` and `uv run reflex db migrate` from the project directory.
- The `status_message` must contain the substring `Validating` while validating, `Reserving` while reserving stock, and `Confirmed` once an order succeeds. On an insufficient-stock failure, `status_message` must contain the substring `Insufficient stock`.
- The computed var `current_step` must return one of exactly these labels: `Idle`, `Validating`, `Reserving`, `Confirmed`, `Failed` (it should be `Confirmed` after a successful checkout and `Failed` after a failed one).
- Run the app in development mode with `uv run reflex run` from the project directory; the frontend is served on port 3000 and the backend on port 8000.
- You may start a dev server (or other background processes) while developing, but you MUST kill all background servers/processes you started before finishing the task, so the evaluation starts from a clean state.

## Interface (long-running app)
- Start command: `uv run reflex run` (run from `/home/user/checkout_app`)
- Frontend port: 3000
- Backend port: 8000
- Browser-checkable: navigating to `http://localhost:3000` renders a page whose content includes the heading text `Checkout` and a `Place Order` button.

