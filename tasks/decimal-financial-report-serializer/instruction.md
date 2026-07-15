# Financial Ledger Report with Custom Serializers (Reflex)

## Background
You are building a single-page financial ledger report using the **Reflex** Python web framework. The ledger stores monetary amounts as `decimal.Decimal` and entry timestamps as `datetime.datetime` directly in the app state. These types are **not** JSON-serializable into the presentation format you need, so the state cannot be synchronized to the browser until you register custom serializers for them. The report renders a ledger table with a computed running balance and computed totals, and lets the user append new entries.

## Requirements
- Build a Reflex app whose state stores a list of ledger entries. Each entry has a text description, an amount held as a `decimal.Decimal`, and a timestamp held as a `datetime.datetime`.
- Register custom serializers (using Reflex's serializer mechanism) so that:
  - Every `decimal.Decimal` amount is presented as a 2-decimal-place currency string.
  - Every `datetime.datetime` is presented as a `YYYY-MM-DD HH:MM` string (24-hour clock).
- Seed the state so that on first load the ledger contains exactly these four entries, in this order:
  1. `Opening balance`, amount `1000.00`, timestamp `2024-01-01 09:00`
  2. `Grocery store`, amount `-234.56`, timestamp `2024-01-02 14:30`
  3. `Salary`, amount `2500.00`, timestamp `2024-01-05 08:00`
  4. `Electric bill`, amount `-89.99`, timestamp `2024-01-10 16:45`
- Render a ledger table with the columns, in order: Description, Amount, Timestamp, Balance. Iterate over the entries in state to build the rows (do not hardcode the rows).
- Add a computed **running balance** for each row: the cumulative sum of all amounts from the first entry through that row, in listed order. Display it in the Balance column, using the same currency formatting.
- Add computed totals displayed below/around the table:
  - Total credits: the sum of all positive amounts.
  - Total debits: the sum of the absolute values of all negative amounts (shown as a positive amount).
  - Net balance: the sum of all amounts.
- Provide an input for a description, an input for an amount, and a button to add a new entry. Adding an entry parses the amount into a `decimal.Decimal`, appends a new entry using the current time as its timestamp, and updates the table, the running balances, and the totals reactively.

## Implementation Hints
- Manage the Python environment with `uv` (the project must run via `uv run reflex run`). Some Reflex dependencies conflict with system packages, so do not rely on the system Python.
- Initialize the project non-interactively with the blank template (`uv run reflex init --template blank`).
- Store the raw `Decimal` / `datetime` values in state and let the registered serializers do the formatting; the same serializers should apply to computed values (running balance and totals) because they are also `Decimal`.
- Use Reflex's iterable rendering to build table rows from the state list, and computed vars for the running balances and totals.
- Currency string format (hard requirement, must match exactly): group thousands with commas and always show exactly two decimals. A zero or positive value `V` is rendered as `$` followed by the grouped number (e.g. `1000.00` -> `$1,000.00`, `2500` -> `$2,500.00`). A negative value is rendered with a leading minus sign before the dollar sign using its absolute value (e.g. `-234.56` -> `-$234.56`, `-89.99` -> `-$89.99`).
- The add-entry inputs must accept a signed decimal amount string (for example values like `50.25` or `-12.00`). The description input, amount input, and add button must be visible and usable on the page at `/`.
- Reflex serves the compiled frontend on port `3000` and the backend on port `8000`; the table data is hydrated into the browser at runtime over the websocket connection.
- Project path: /home/user/financial_ledger
- Start command: `uv run reflex run` (run from the project path)
- Frontend URL to open in a browser: http://localhost:3000
- IMPORTANT: If you start the Reflex dev server (or any other server) in the background to test your work, you MUST kill all such background servers before you finish, leaving no process listening on ports 3000 or 8000.

