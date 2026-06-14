# Multi-Step Registration Wizard with LocalStorage Persistence

## Background
Build a four-step registration wizard with the [Reflex](https://reflex.dev/) full-stack Python framework. The wizard must use dynamic routing for each step, enforce explicit per-step validation, persist the in-progress form into `rx.LocalStorage` so a browser refresh resumes at the last saved step, and write the final submission into a SQLite table.

## Requirements
- The application is a single Reflex project rooted at `/home/user/wizard_app`.
- Use `uv` to create and manage the Python environment (the system `python3` does not have Reflex installed).
- Use the Reflex `blank` template to scaffold the project non-interactively.
- Implement a single dynamic page at the route `/wizard/[step]` that renders one of four steps based on the `step` URL segment:
  1. `profile` — collect `full_name` and `email`.
  2. `address` — collect `street`, `city`, and `postal_code`.
  3. `preferences` — collect `newsletter` (boolean), `theme` (`light` or `dark`), and `language` (ISO 639-1 two-letter code).
  4. `review` — render a summary of all previously entered data and a Submit button.
- Every step page must display a textual step indicator of the exact form `Step N of 4` (where N is 1–4).
- Validation rules (applied both when advancing in the UI and when called through the backend HTTP endpoint described below):
  - `full_name`: 1 to 100 characters after stripping whitespace.
  - `email`: must match the regex `^[^@\s]+@[^@\s]+\.[^@\s]+$`.
  - `street`: 1 to 200 characters after stripping whitespace.
  - `city`: 1 to 100 characters after stripping whitespace.
  - `postal_code`: exactly 5 ASCII digits.
  - `newsletter`: boolean.
  - `theme`: one of `light` or `dark`.
  - `language`: exactly two lowercase ASCII letters.
- Persist the in-progress form data into `rx.LocalStorage` under the storage key name `wizard_draft`. The value must be a single JSON object string containing exactly these keys: `full_name`, `email`, `street`, `city`, `postal_code`, `newsletter`, `theme`, `language`, `current_step`. Unfilled string fields default to the empty string, `newsletter` defaults to `false`, and `current_step` is one of `profile`, `address`, `preferences`, `review`.
- The page must hydrate from `wizard_draft` on load so refreshing the browser resumes at the last saved step with previously entered data.
- On final submission, insert one row into a SQLite table named `submission` inside `/home/user/wizard_app/reflex.db` with these columns (any compatible SQL types are acceptable): `id` (auto-incrementing primary key), `full_name`, `email`, `street`, `city`, `postal_code`, `newsletter`, `theme`, `language`, `created_at` (ISO-8601 timestamp string).
- Mount a small FastAPI router on the Reflex backend (port 8000) using the `api_transformer` parameter of `rx.App(...)`. Expose exactly one JSON endpoint:
  - `POST /api/wizard/submit`
    - Request JSON body keys: `full_name`, `email`, `street`, `city`, `postal_code`, `newsletter`, `theme`, `language`.
    - On any validation failure, respond with HTTP `400` and a JSON body of the form `{"errors": {"<field>": "<message>", ...}}` listing every offending field.
    - On success, insert the row into the `submission` table and respond with HTTP `200` and a JSON body `{"id": <int>}` containing the new row's primary key.

## Implementation Hints
- Refer to the Reflex docs for [Dynamic Routing](https://reflex.dev/docs/pages/dynamic-routing/), [Client Storage](https://reflex.dev/docs/client-storage/overview/), [Browser Storage API](https://reflex.dev/docs/api-reference/browser-storage/), [Database Overview](https://reflex.dev/docs/database/overview/), and [API Routes Overview](https://reflex.dev/docs/api-routes/overview/).
- The Reflex blank template can be created non-interactively with `uv run reflex init --template blank`.
- The same validation logic should drive both the UI Next-step gate and the HTTP `submit` endpoint to keep the behavior consistent.
- Use Reflex's `rx.Model` with `table=True` and `reflex db init` / `reflex db makemigrations` / `reflex db migrate` to create the SQLite schema before starting the app.
- The application is started with `uv run reflex run` which serves the frontend on port 3000 and the backend (including FastAPI routes) on port 8000.
- After you are done, **stop any Reflex servers you started in the background** (e.g., `pkill -f "reflex run"`). The verifier will start its own server.

## Acceptance Criteria
- Project path: `/home/user/wizard_app`
- Start command: `cd /home/user/wizard_app && uv run reflex run`
- Frontend port: `3000`
- Backend port: `8000`
- SQLite database file: `/home/user/wizard_app/reflex.db`
- Submission table name: `submission`
- Routes (frontend, port 3000) — each must respond with HTTP `200` and the response body must contain the literal step indicator text:
  - `GET /wizard/profile` → body contains `Step 1 of 4`
  - `GET /wizard/address` → body contains `Step 2 of 4`
  - `GET /wizard/preferences` → body contains `Step 3 of 4`
  - `GET /wizard/review` → body contains `Step 4 of 4`
- LocalStorage configuration:
  - The Reflex state must declare a `rx.LocalStorage` var whose key name (the storage key visible in the browser) is exactly `wizard_draft`.
  - The value stored in `wizard_draft` is a single JSON string with the schema `{"full_name": str, "email": str, "street": str, "city": str, "postal_code": str, "newsletter": bool, "theme": str, "language": str, "current_step": str}`.
- HTTP API (backend, port 8000):
  - `POST /api/wizard/submit`
    - Request body shape:
      ```json
      {
        "full_name": string,
        "email": string,
        "street": string,
        "city": string,
        "postal_code": string,
        "newsletter": boolean,
        "theme": string,
        "language": string
      }
      ```
    - On validation failure: HTTP `400`, JSON body shape `{"errors": {"<field>": "<message>"}}`. The keys in `errors` must include every invalid field.
    - On success: HTTP `200`, JSON body shape `{"id": integer}`, and a corresponding row in the `submission` table.
- Background servers started during the task **must be stopped** before completion; the verifier starts its own server.

