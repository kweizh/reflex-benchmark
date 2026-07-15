# Sales Report with Filters and CSV Export (Reflex)

## Background
You are building a small internal analytics page with the **Reflex** Python web framework. The page shows a sales report backed by a local **SQLite** database. A user narrows the report with a **Category** filter and a **Date** filter, sees the matching rows in a table together with a live summary (row count and total amount), and can export exactly the currently-filtered rows as a **CSV file** using Reflex's download event primitive.

The project has already been scaffolded with `uv` and the `reflex` package, and a blank Reflex app has been initialized. Your job is to implement the report page and its state logic.

## Requirements
- Define a database model (via `rx.Model`, `table=True`) for a sale with the fields: `date` (string, ISO `YYYY-MM-DD`), `category` (string), `product` (string), `quantity` (integer), and `amount` (float, the line total for that sale).
- Seed the SQLite database with **exactly** the following 7 rows (and no others). Seeding must be **idempotent**: restarting the app MUST NOT create duplicate rows.

  | date | category | product | quantity | amount |
  | --- | --- | --- | --- | --- |
  | 2024-01-15 | Electronics | USB Cable | 3 | 30.00 |
  | 2024-01-15 | Electronics | Mouse | 2 | 50.00 |
  | 2024-01-15 | Books | Python 101 | 4 | 120.00 |
  | 2024-01-15 | Clothing | T-Shirt | 5 | 100.00 |
  | 2024-01-16 | Electronics | Keyboard | 1 | 80.00 |
  | 2024-01-16 | Books | SQL Guide | 2 | 60.00 |
  | 2024-01-16 | Books | Web Dev | 3 | 90.00 |

- The index page (`/`) must contain two dropdown selectors:
  - A **Category** selector with the options `All Categories`, `Books`, `Clothing`, `Electronics` (default `All Categories`).
  - A **Date** selector with the options `All Dates`, `2024-01-15`, `2024-01-16` (default `All Dates`).
  - `All Categories` / `All Dates` mean "do not filter on that field".
- Whenever a filter changes, query the database for the matching rows and display them in a table with the columns `date`, `category`, `product`, `quantity`, `amount` (in that order), ordered by ascending row id (insertion order).
- Show a live summary derived from the filtered rows: the number of matching rows and the total amount (the sum of the `amount` column). Both summary values MUST be implemented as computed vars.
- When no rows match the current filters, hide the table and instead show the exact text `No sales match the selected filters.`
- Provide an **Export CSV** button that downloads the currently-filtered rows as a CSV file using Reflex's download event. Generate the CSV bytes in the event handler.

## Implementation Hints
- Project path: `/home/user/sales_report` (a blank Reflex app named `sales_report` is already initialized here; edit `sales_report/sales_report.py` and run DB migrations).
- Use `uv` to manage the environment (e.g. `uv run reflex ...`). The dev server serves the frontend on **port 3000** and the backend on **port 8000**.
- Query the database inside event handlers with `rx.session()` and SQLModel-style `select().where(...)`. Store the filtered rows in a base var and derive the count and total with `@rx.var` computed vars.
- Render the filtered rows with `rx.foreach`, use `rx.cond` for the empty state, and wire each selector's `on_change` to an event handler that accepts the selected value as an argument.
- For the export, return `rx.download(data=<csv bytes/str>, filename="sales_report.csv")` from an event handler. The CSV MUST start with the exact header line `date,category,product,quantity,amount`, followed by one line per currently-filtered row in ascending id order, where `amount` is formatted with exactly two decimal places (e.g. `30.00`) and `quantity` is an integer. When no rows match, the CSV contains only the header line.
- Start command (for verification): `cd /home/user/sales_report && uv run reflex run`.
- IMPORTANT: Any background/dev server you start during your own testing MUST be killed before you finish. Do not leave any process listening on ports 3000 or 8000 when you are done; the automated verification starts its own server.

