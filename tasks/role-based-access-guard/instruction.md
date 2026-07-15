# Role-Based Page Access Guard in Reflex

## Background
You are building the access-control layer of an internal tool with the **Reflex** Python web framework. There is **no external auth provider** — users are seeded locally and their credentials are stored on the backend only. Access to pages is enforced entirely with Reflex page **`on_load`** event guards that redirect unauthenticated or unauthorized visitors, using the framework's built-in state and routing primitives.

## Requirements
Implement a multi-page Reflex application that enforces role-based access:

- A public **login** page at `/login` with a username field, a password field, and a submit control. On valid credentials it establishes the session and redirects the visitor to `/dashboard`. On invalid credentials it stays on `/login` and shows a visible error message containing the text `Invalid credentials`.
- A protected **dashboard** page at `/dashboard` available to any authenticated user. If a visitor is not authenticated, the page's load guard must redirect them to `/login`. When authenticated it displays the text `Dashboard`, together with the logged-in username and the user's role.
- A protected **admin** page at `/admin` available only to users whose role is `admin`. Its load guard must redirect unauthenticated visitors to `/login`, and authenticated non-admin visitors to `/forbidden`. When an admin views it, it displays the text `Admin Panel`.
- A public **forbidden** page at `/forbidden` that displays the text `Access Denied`.
- A **logout** control on the dashboard that clears the current session and returns the visitor to `/login`.

Seed exactly two users into the app at startup (these are the only accounts that exist):

| username | password | role |
|----------|----------------|-------|
| `admin`  | `s3cure-admin-pw` | `admin` |
| `alice`  | `s3cure-user-pw`  | `user`  |

## Implementation Hints
- Use `uv` to manage the Python environment. Initialize the project with the **blank** template non-interactively (e.g. `uv init`, `uv add reflex`, `uv run reflex init --template blank`).
- Enforce access with the page-load event guard pattern: attach an `on_load` event handler to each protected page (via the `@rx.page(on_load=...)` decorator or `app.add_page(..., on_load=...)`) and `return rx.redirect(<path>)` from that handler when the visitor is not allowed.
- Keep secrets on the backend: store the seeded credentials and the current session's user and role in **backend-only** state (attributes prefixed with `_`, which Reflex never sends to the client). Derive authorization decisions (e.g. whether the visitor is authenticated and whether they are an admin) with **computed vars**.
- **Never store or compare plaintext passwords.** Hash each seeded password locally using a locally-generated salt (e.g. with Python's `hashlib`/`secrets`); do not read any secret from environment variables and do not call any external service.
- The application must rely on **local services only** — the Reflex dev server (frontend on port `3000`, backend on port `8000`). Do not add any external dependency, network call, database service, or auth provider.
- Run the app in development mode with `uv run reflex run`. The frontend is served on port `3000` and the backend on port `8000`.
- Page text requirements (must appear on the rendered page): `/dashboard` shows `Dashboard`; `/admin` shows `Admin Panel`; `/forbidden` shows `Access Denied`; a failed login shows `Invalid credentials`.
- Project path: `/home/user/role_guard`
- Start command: `uv run reflex run`
- Ports: frontend `3000`, backend `8000`
- If you start the Reflex server (or any other server) in the background to test your work, you **must kill all such background servers before finishing** so that no server process is left running.

## Notes
The app is evaluated by driving the running site in a browser and by inspecting the served frontend assets. Make sure a fresh browser session starts unauthenticated and that the plaintext passwords are never embedded in the compiled frontend that is sent to the browser.

