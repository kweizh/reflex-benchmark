# Shopping Cart with Computed Totals (Reflex)

## Background
Build an interactive shopping cart web application using the Reflex pure-Python full-stack framework. Shoppers pick products from a fixed local catalog, adjust quantities, apply a discount code, and see live-updating price totals. The cart must survive a page refresh by persisting to the browser's local storage. Everything runs locally — there are no external services, APIs, databases, or network calls of any kind.

## Requirements
- A fixed, locally hard-coded product catalog. Each product has a name and a price. Provide at least 4 products.
- Users can add a product to the cart, remove a product from the cart, and increase/decrease the quantity of a product already in the cart.
- Show live totals that update automatically as the cart changes: subtotal, discount, tax, and grand total. These must be Reflex computed vars.
- A discount-code text input with an "Apply" button. Applying a code runs an event handler that validates it against a set of locally-defined codes. A valid code applies its percentage discount; an invalid code applies no discount and shows an error message. Discount codes are hard-coded locally (never validated against any external service).
- Persist the current cart to the browser's local storage so it survives a page refresh, and restore it when the page loads.
- When the cart is empty, show an empty-cart message. When it has items, render the item rows dynamically.

## Implementation Hints
- Use `uv` to manage the Python environment. A blank Reflex project has already been created and its dependencies installed at the project path below; implement your app inside it.
- Keep all pricing and discount logic in a dedicated, self-contained pure-Python module so it can be tested without importing Reflex (import only the Python standard library there — no `reflex` import).
- Use Reflex computed vars (`@rx.var`) for the derived totals, event handlers (including at least one that takes an argument, such as the product identity) for cart mutations, `rx.foreach` to render cart rows, and `rx.cond` for the empty-cart state.
- Use `rx.LocalStorage` for client-side persistence and a page `on_load` event to restore the saved cart. Because local storage holds strings, serialize the cart (for example, as JSON).

Hard requirements (must match exactly):
- Project path: `/home/user/shopping_cart`
- Implement the Reflex UI and state in `/home/user/shopping_cart/shopping_cart/shopping_cart.py`.
- Put the pricing logic in `/home/user/shopping_cart/shopping_cart/cart_core.py`, importing only the Python standard library. It must expose:
  - `TAX_RATE`: a float equal to `0.08`.
  - `DISCOUNT_CODES`: a `dict` mapping an upper-case code string to its fractional discount rate, including at least `"SAVE10": 0.10`, `"SAVE20": 0.20`, and `"WELCOME5": 0.05`.
  - `compute_totals(items, code="")`: `items` is a list of dicts, each with keys `name` (str), `price` (float), and `quantity` (int). It returns a dict with exactly the keys `subtotal`, `discount`, `tax`, and `total`, each a number rounded to 2 decimals, where:
    - `subtotal` = sum of `price * quantity` over all items,
    - `discount` = `subtotal * rate` when `code` matches a discount code (matching is case-insensitive), otherwise `0`,
    - `tax` = `(subtotal - discount) * TAX_RATE`,
    - `total` = `subtotal - discount + tax`.
  - An empty cart (no items) must yield `subtotal`, `discount`, `tax`, and `total` all equal to `0`.
- The Reflex state must compute the displayed subtotal, discount, tax, and grand total through computed vars that reuse `compute_totals` from `cart_core`.
- The page served at `/` must include the visible heading text `Shopping Cart`, and while the cart is empty it must display the text `Your cart is empty`.
- Start command (run from the project path): `uv run reflex run`
- Ports: frontend `3000`, backend `8000`.
- After you finish, stop any dev servers you started so that ports `3000` and `8000` are free. The evaluation will start its own server when it needs one.

