# NumPy ndarray Custom Serializer Powering a Recharts Line Chart

## Background
Reflex synchronizes Python state to the React frontend by JSON-serializing every Base Var. Storing a raw `numpy.ndarray` in a regular state field raises `reflex.utils.exceptions.VarTypeError` at compile/runtime because numpy arrays are not directly JSON-serializable. The idiomatic fix is to register a `@rx.serializer` for `numpy.ndarray` that converts it into a primitive structure consumable by `rx.recharts.line_chart`. Your job is to build such an app end to end.

## Requirements
- A Reflex application that renders an interactive line chart driven by a `numpy.ndarray` state var.
- The state must keep the data as a **typed `numpy.ndarray`** of shape `(50, 2)` (column 0 is `x`, column 1 is `y`).
- A `@rx.serializer` must be registered for `numpy.ndarray` that converts it into a `list[dict[str, float]]` whose every element looks like `{"x": <float>, "y": <float>}` (those exact lowercase keys, plain `float` values).
- The home page (`/`) must mount an `rx.recharts.line_chart` bound to that ndarray state var, with at least one `rx.recharts.line(data_key="y")` series and an `rx.recharts.x_axis(data_key="x")`.
- The page must include a button labelled exactly `Regenerate` that, when clicked, replaces the state var with a fresh array of 50 noisy sine-wave points.
- The app must also expose a custom FastAPI route `GET /api/points` (mounted through `rx.App(api_transformer=...)`) that returns a JSON array produced by the same noisy-sine generator function used by the state, serialized in the same `[{"x": float, "y": float}, ...]` shape with exactly 50 entries. Each call must produce a fresh array (use randomness, not a cached value).
- The environment must be managed with `uv` per the repository convention. After the verifier finishes, no background Reflex processes (frontend on port 3000, backend on port 8000) may remain.

## Implementation Hints
- Use `uv init` + `uv add reflex numpy` and the `--template blank` flag for `reflex init`.
- Register the serializer with `@rx.serializer` on a function annotated `def serialize_ndarray(arr: numpy.ndarray) -> list[dict[str, float]]:` so Reflex picks up the type from the annotation.
- The noisy sine generator should produce points where `x` spans a deterministic-shape range (e.g. evenly spaced floats) and `y = sin(x) + small_noise`; use `numpy.random` so each invocation is genuinely different.
- For the custom REST route, build a `FastAPI()` instance, add a `@app.get("/api/points")` handler that calls the same generator, then pass it to `rx.App(api_transformer=fastapi_app)`.
- The `rx.recharts.line_chart` `data=` prop should be bound directly to the typed ndarray var — Reflex will pipe the value through the registered serializer automatically, so you must NOT pre-convert it to a list inside the component tree.
- Provide a `bash start.sh` at the project root that prepares the environment (`uv sync`, `uv run reflex init --template blank` if `.web` is missing, `uv run reflex db init` / `makemigrations` / `migrate` if needed) and then launches `uv run reflex run --loglevel info`. The verifier will execute this script and then poll the backend `/ping` endpoint.
- Provide a `bash stop.sh` that kills anything bound to ports 3000 and 8000 so the verifier can guarantee teardown.

## Acceptance Criteria
- Project path: `/home/user/numpy_chart_serializer`.
- Start command: `bash start.sh` (run from the project root, must launch both backend on port 8000 and frontend on port 3000).
- Stop command: `bash stop.sh` (must terminate every process bound to ports 3000 and 8000).
- Frontend port: 3000.
- Backend port: 8000.
- The Python environment is managed by `uv`; `pyproject.toml` (or equivalent uv-managed manifest) lists `reflex` and `numpy` as dependencies.
- At least one `.py` file inside the project declares a State base var whose type annotation references `numpy.ndarray` (e.g. `points: numpy.ndarray = ...`) — backend-only underscore-prefixed fields do NOT satisfy this requirement; the var must be a synchronized base var.
- At least one `.py` file inside the project defines a function decorated with `@rx.serializer` whose single argument is annotated `numpy.ndarray` (or `np.ndarray`) and whose return annotation resolves to `list[dict[str, float]]` (or an equivalent typing alias).
- HTTP GET `http://localhost:8000/ping/` returns status 200 with body `"pong"`.
- HTTP GET `http://localhost:3000/` returns status 200 (page renders without a `VarTypeError` traceback in the response body or backend logs).
- HTTP GET `http://localhost:8000/api/points` returns:
  - status 200,
  - Content-Type `application/json`,
  - a JSON array of length exactly 50,
  - every element is an object with exactly two keys `x` and `y`, both numeric (JSON numbers).
- Two successive calls to `GET http://localhost:8000/api/points` return arrays whose contents differ (the regeneration is genuinely random).
- The rendered home page HTML contains a button with the exact visible label `Regenerate`.
- After `bash stop.sh` is executed, neither port 3000 nor port 8000 has any listener.

