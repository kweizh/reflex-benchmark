You need to display a large directory of users stored in a Reflex-managed SQLite database without blocking the main event loop.

You need to implement an asynchronous background event handler (`fetch_users`) that queries the `User` model asynchronously and updates the UI state with a chunked/paginated list of users.

**Constraints:**
- The database model MUST inherit from `rx.Model, table=True`.
- You must use `rx.asession()` to execute the database query asynchronously.
- The database query result must be parsed and applied to the synchronized state variables only within an `async with self:` block.