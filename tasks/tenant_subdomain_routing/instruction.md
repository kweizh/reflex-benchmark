# Multi-Tenant Path-Based Routing with FastAPI Middleware (Reflex)

## Background
Build a Reflex web application that exposes tenant-scoped pages under `/t/[tenant_id]/...` and a tenant-aware REST endpoint mounted onto Reflex's internal FastAPI backend through `api_transformer`. The application MUST be implemented at `/home/user/myproject` using `uv` to manage the Python environment per the framework documentation.

## Requirements
- Pure-Python full-stack application built with Reflex.
- A SQLite-backed `Tenant` table (using `rx.Model`) with the following exact seed rows. The application MUST insert these rows on startup if they do not already exist:
  - slug=`acme`, name=`Acme Corp`
  - slug=`globex`, name=`Globex Inc`
  - slug=`initech`, name=`Initech LLC`
- Two dynamic-route pages:
  - `/t/[tenant_id]/dashboard`
  - `/t/[tenant_id]/settings`
  Both pages MUST resolve the tenant by reading the dynamic route segment from the Reflex router (e.g. the `tenant_id` dynamic var exposed on `rx.State`, or the equivalent value derived from `self.router`). The tenant lookup MUST happen via an on-load event handler that queries the `Tenant` table where `slug == tenant_id`.
- When the tenant exists, the rendered page for `/t/[tenant_id]/dashboard` MUST display the literal tenant name AND the literal text `Dashboard`. The rendered page for `/t/[tenant_id]/settings` MUST display the literal tenant name AND the literal text `Settings`.
- When the tenant does NOT exist, both pages MUST render a 404 marker. The page MUST display the case-sensitive literal text `Tenant Not Found` and MUST NOT display any of the seed tenant names. The 404 branch MUST be controlled by `rx.cond` based on whether the tenant lookup succeeded.
- A FastAPI application MUST be mounted onto the Reflex backend through the `api_transformer` parameter of `rx.App`. The FastAPI app MUST:
  - Register an ASGI/HTTP middleware that inspects every incoming request whose path starts with `/api/`. The middleware MUST look up the value of the request header `X-Tenant-Id` against the `Tenant` table and short-circuit with HTTP `403` and a JSON body of `{"detail": "forbidden"}` if the header is missing or does not match any known tenant slug. Requests to non-`/api/` paths MUST pass through unmodified so that Reflex's own routes (frontend assets, `/ping`, `/_event`, websocket) keep working.
  - Expose `GET /api/me`. When the middleware allows the request through, this endpoint MUST return HTTP `200` with a JSON body `{"slug": <tenant_slug>, "name": <tenant_name>}` matching the tenant identified by the `X-Tenant-Id` header.

## Implementation Hints
- Initialize the project non-interactively with `uv` and the Reflex `blank` template, then run `reflex db init`, `reflex db makemigrations`, and `reflex db migrate` to apply the schema. Use the default Reflex SQLite database under the project directory.
- The middleware is plain FastAPI/Starlette; it only needs to read the same SQLite database that `rx.Model` writes to (no shared Reflex state).
- Page on-load handlers may use `rx.session()` (synchronous) to look up tenants by slug.

## Acceptance Criteria
- Project path: /home/user/myproject
- Start command: `cd /home/user/myproject && uv run reflex run --env prod`
- Ports:
  - Frontend (Next.js, browser-facing): `3000`
  - Backend (FastAPI / Reflex websocket): `8000`
- The verifier starts its own server using the start command above. The agent MUST shut down any background processes it started for development or testing before finishing the task.
- Browser-visible routes (port 3000):
  - `http://localhost:3000/t/acme/dashboard` → page displays `Acme Corp` and `Dashboard` (no `Tenant Not Found`).
  - `http://localhost:3000/t/globex/settings` → page displays `Globex Inc` and `Settings` (no `Tenant Not Found`).
  - `http://localhost:3000/t/initech/dashboard` → page displays `Initech LLC` and `Dashboard`.
  - `http://localhost:3000/t/no-such-tenant/dashboard` → page displays `Tenant Not Found` and does NOT display any of `Acme Corp`, `Globex Inc`, or `Initech LLC`.
- Backend API endpoints (port 8000):
  - `GET http://localhost:8000/api/me` with header `X-Tenant-Id: acme` → HTTP 200, JSON body `{"slug": "acme", "name": "Acme Corp"}`.
  - `GET http://localhost:8000/api/me` with header `X-Tenant-Id: initech` → HTTP 200, JSON body `{"slug": "initech", "name": "Initech LLC"}`.
  - `GET http://localhost:8000/api/me` with no `X-Tenant-Id` header → HTTP 403, JSON body `{"detail": "forbidden"}`.
  - `GET http://localhost:8000/api/me` with header `X-Tenant-Id: not-a-tenant` → HTTP 403, JSON body `{"detail": "forbidden"}`.
- Reflex's reserved backend route MUST keep working: `GET http://localhost:8000/ping` → HTTP 200 with body `"pong"`.

