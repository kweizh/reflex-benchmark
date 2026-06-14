"""Multi-tenant Reflex application with path-based routing."""

from __future__ import annotations

import reflex as rx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlmodel import Field as SQLModelField
from starlette.types import ASGIApp, Receive, Scope, Send

# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------


class Tenant(rx.Model, table=True):
    """A tenant in the system."""

    slug: str = SQLModelField(unique=True, index=True)
    name: str


# ---------------------------------------------------------------------------
# Reflex state for tenant pages
# ---------------------------------------------------------------------------


class TenantState(rx.State):
    """State for tenant-scoped pages."""

    tenant_name: str = ""
    tenant_found: bool = False

    def load_tenant(self) -> None:
        """Look up the tenant by slug from the dynamic route param."""
        slug = self.tenant_id  # type: ignore[attr-defined]
        with rx.session() as sess:
            tenant = sess.exec(Tenant.select().where(Tenant.slug == slug)).first()
            if tenant is not None:
                self.tenant_name = tenant.name
                self.tenant_found = True
            else:
                self.tenant_name = ""
                self.tenant_found = False


# ---------------------------------------------------------------------------
# Page components
# ---------------------------------------------------------------------------


def dashboard() -> rx.Component:
    """Dashboard page for a tenant."""
    return rx.container(
        rx.cond(
            TenantState.tenant_found,
            rx.vstack(
                rx.heading(TenantState.tenant_name, size="3"),
                rx.text("Dashboard"),
                spacing="4",
                align="center",
                padding_top="2em",
            ),
            rx.vstack(
                rx.heading("Tenant Not Found", size="3"),
                spacing="4",
                align="center",
                padding_top="2em",
            ),
        )
    )


def settings() -> rx.Component:
    """Settings page for a tenant."""
    return rx.container(
        rx.cond(
            TenantState.tenant_found,
            rx.vstack(
                rx.heading(TenantState.tenant_name, size="3"),
                rx.text("Settings"),
                spacing="4",
                align="center",
                padding_top="2em",
            ),
            rx.vstack(
                rx.heading("Tenant Not Found", size="3"),
                spacing="4",
                align="center",
                padding_top="2em",
            ),
        )
    )


# ---------------------------------------------------------------------------
# FastAPI sub-app with tenant middleware
# ---------------------------------------------------------------------------

_fastapi_app = FastAPI()


@_fastapi_app.get("/api/me")
def api_me(request: Request):
    """Return tenant info based on X-Tenant-Id header (middleware already validated)."""
    tenant_slug = request.headers.get("X-Tenant-Id", "")
    tenant_name = request.state.tenant_name
    return JSONResponse({"slug": tenant_slug, "name": tenant_name})


class TenantMiddleware:
    """ASGI middleware that validates X-Tenant-Id for /api/ paths."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Extract X-Tenant-Id from headers
        headers = dict(scope.get("headers", []))
        tenant_id_bytes = headers.get(b"x-tenant-id")
        if tenant_id_bytes is None:
            response = JSONResponse({"detail": "forbidden"}, status_code=403)
            await response(scope, receive, send)
            return

        tenant_id = tenant_id_bytes.decode("latin-1")

        # Look up tenant in the database
        from sqlmodel import Session as SQLModelSession
        from reflex.model import get_engine

        engine = get_engine()
        with SQLModelSession(engine) as db_sess:
            tenant = db_sess.exec(
                Tenant.select().where(Tenant.slug == tenant_id)
            ).first()

        if tenant is None:
            response = JSONResponse({"detail": "forbidden"}, status_code=403)
            await response(scope, receive, send)
            return

        # Stash tenant info on scope state so the endpoint can read it
        scope.setdefault("state", {})
        scope["state"]["tenant_name"] = tenant.name

        await self.app(scope, receive, send)


# Apply middleware to the FastAPI app
_fastapi_app.add_middleware(TenantMiddleware)


# ---------------------------------------------------------------------------
# Seed the database on startup
# ---------------------------------------------------------------------------


def _seed_tenants() -> None:
    """Insert seed tenants if they don't already exist."""
    from sqlmodel import Session as SQLModelSession
    from reflex.model import get_engine

    engine = get_engine()
    with SQLModelSession(engine) as sess:
        for slug, name in [
            ("acme", "Acme Corp"),
            ("globex", "Globex Inc"),
            ("initech", "Initech LLC"),
        ]:
            existing = sess.exec(
                Tenant.select().where(Tenant.slug == slug)
            ).first()
            if existing is None:
                sess.add(Tenant(slug=slug, name=name))
        sess.commit()


# ---------------------------------------------------------------------------
# Build the Reflex app
# ---------------------------------------------------------------------------

app = rx.App(api_transformer=_fastapi_app)

app.add_page(
    dashboard,
    route="/t/[tenant_id]/dashboard",
    title="Dashboard",
    on_load=TenantState.load_tenant,
)

app.add_page(
    settings,
    route="/t/[tenant_id]/settings",
    title="Settings",
    on_load=TenantState.load_tenant,
)

app.register_lifespan_task(_seed_tenants)