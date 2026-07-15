# Reflex Live Metrics Dashboard with a Local FastAPI API Transformer

## Background
Reflex serves your app through an internal FastAPI/ASGI backend. The `api_transformer` initialization parameter of `rx.App` lets you mount your own FastAPI (or Starlette) application onto that same backend so that custom HTTP endpoints are served alongside the Reflex event API on port 8000.

You will build a small, fully self-contained "Live Metrics Dashboard". A custom FastAPI router exposes in-process counters as JSON, and the Reflex frontend continuously polls those local endpoints and renders the counters live. Everything runs locally: there are no external services, databases, or network dependencies of any kind. The only HTTP endpoints involved are the app's own endpoints on `127.0.0.1:8000`.

## Requirements
- Build a custom FastAPI application and mount it onto the Reflex app using the `api_transformer` parameter of `rx.App`.
- The counters are held entirely in process memory (a plain in-memory data structure). There is a fixed set of three counters named `page_view`, `button_click`, and `api_call`, each starting at `0`. The counters reset to `0` whenever the server process restarts.
- The mounted FastAPI app must expose these endpoints on the backend (port 8000):
  - `GET /api/metrics`: return the current counters and their aggregate total.
  - `POST /api/metrics/increment`: increment a named counter by a given amount and return the updated value.
- The Reflex frontend must poll `GET /api/metrics` from the app's own local backend on a recurring interval (using a background event task that acquires the state lock to store results), so the displayed numbers update live without a manual refresh. The dashboard itself must only read via `GET /api/metrics`; it must never mutate the counters on its own. Counters change only through the `POST /api/metrics/increment` endpoint.
- Use a Reflex computed var to derive a displayed aggregate (the total across all counters) and use `rx.foreach` to render one row per counter from the polled data.

## Implementation Hints
- Use `uv` to manage the Python environment for the project. The project is already initialized at the project path with the blank Reflex template and `reflex` added as a dependency; run all Reflex commands with `uv run` (e.g. `uv run reflex run`).
- Provide the custom endpoints by constructing a `fastapi.FastAPI()` instance, adding your routes to it, and passing it as `rx.App(api_transformer=...)`.
- For live updates, drive polling from a background task decorated with `@rx.event(background=True)`; remember that a background task may only mutate state inside an `async with self:` block. Start polling from a page `on_load` handler. The frontend should read the app's own endpoint at `http://127.0.0.1:8000/api/metrics`.
- Keep all counter state in ordinary in-process Python memory owned by the FastAPI layer; do not use any external datastore.
- Project path: /home/user/metrics_app
- Start command (from the project path): `uv run reflex run`
- Backend (FastAPI + Reflex event) port: 8000
- Frontend port: 3000
- The browser tab / page title of the dashboard page must be exactly `Live Metrics Dashboard`, and that exact string must also be rendered as visible text (e.g. a heading) on the page.
- API contract (served on `http://127.0.0.1:8000`):
  - `GET /api/metrics`: returns status 200 and a JSON object with exactly the keys `counters` and `total`. `counters` is a JSON object mapping each counter name to its integer value; `total` is the integer sum of all counter values.

    ```json
    // Response
    {
      "counters": { "page_view": 0, "button_click": 0, "api_call": 0 },
      "total": 0
    }
    ```

  - `POST /api/metrics/increment`: accepts a JSON body with a required string `name` and an optional integer `amount` (default `1`). It increments the named counter by `amount` and returns status 200 with a JSON object with exactly the keys `name`, `value`, and `total`, where `value` is the counter's new value and `total` is the new aggregate sum.

    ```json
    // Request
    { "name": "page_view", "amount": 1 }
    ```
    ```json
    // Response
    { "name": "page_view", "value": 1, "total": 1 }
    ```

  - If `name` is not one of the three known counters, `POST /api/metrics/increment` must return status 404.
- After you finish and verify your work, you MUST stop/kill every background process or server you started (for example any `reflex run` dev server), leaving no listening process on ports 3000 or 8000. The evaluation will start its own server.

