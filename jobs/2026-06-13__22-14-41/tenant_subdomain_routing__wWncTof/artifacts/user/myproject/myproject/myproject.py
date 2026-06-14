"""Multi-tenant Reflex application with path-based routing and API middleware."""

import reflex as rx
from sqlmodel import select
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware

from rxconfig import config
from .models import Tenant, seed_tenants


class TenantState(rx.State):
    """State that holds the resolved tenant for the current page."""

    tenant_name: str = ""
    tenant_slug: str = ""
    is_loaded: bool = False

    def load_tenant(self):
        """Look up the tenant by the dynamic route segment and store it."""
        # self.tenant_id is a computed var from the route [tenant_id]
        slug = self.tenant_id  # type: ignore[attr-defined]
        with rx.session() as session:
            tenant = session.exec(
                select(Tenant).where(Tenant.slug == slug)
            ).first()
        if tenant:
            self.tenant_name = tenant.name
            self.tenant_slug = tenant.slug
        self.is_loaded = True

    @rx.var
    def tenant_found(self) -> bool:
        """Whether the tenant was found."""
        return bool(self.tenant_name)


# ── FastAPI sub-application with tenant-aware middleware ──────────────────────

class TenantMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that validates X-Tenant-Id for /api/ paths."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            tenant_id = request.headers.get("X-Tenant-Id")
            if not tenant_id:
                return JSONResponse(
                    status_code=403, content={"detail": "forbidden"}
                )
            # Look up tenant in the same SQLite database
            with rx.session() as session:
                tenant = session.exec(
                    select(Tenant).where(Tenant.slug == tenant_id)
                ).first()
            if not tenant:
                return JSONResponse(
                    status_code=403, content={"detail": "forbidden"}
                )
            # Attach tenant info to request state for the endpoint
            request.state.tenant_slug = tenant.slug
            request.state.tenant_name = tenant.name
        return await call_next(request)


def create_api_app() -> Starlette:
    """Create a FastAPI/Starlette app with the tenant middleware and /api/me endpoint."""
    api_app = Starlette()

    async def me_endpoint(request: Request):
        return JSONResponse({
            "slug": request.state.tenant_slug,
            "name": request.state.tenant_name,
        })

    api_app.add_route("/api/me", me_endpoint, methods=["GET"])
    api_app.add_middleware(TenantMiddleware)

    return api_app


# ── Pages ─────────────────────────────────────────────────────────────────────

def dashboard() -> rx.Component:
    """Dashboard page for a tenant."""
    return rx.container(
        rx.vstack(
            rx.cond(
                TenantState.tenant_found,
                rx.fragment(
                    rx.heading(TenantState.tenant_name, size="8"),
                    rx.text("Dashboard", size="5"),
                ),
                rx.cond(
                    TenantState.is_loaded,
                    rx.heading("Tenant Not Found", size="8"),
                    rx.text("Loading..."),
                ),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


def settings() -> rx.Component:
    """Settings page for a tenant."""
    return rx.container(
        rx.vstack(
            rx.cond(
                TenantState.tenant_found,
                rx.fragment(
                    rx.heading(TenantState.tenant_name, size="8"),
                    rx.text("Settings", size="5"),
                ),
                rx.cond(
                    TenantState.is_loaded,
                    rx.heading("Tenant Not Found", size="8"),
                    rx.text("Loading..."),
                ),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


# ── App ───────────────────────────────────────────────────────────────────────

app = rx.App(
    api_transformer=create_api_app(),
)

app.add_page(
    dashboard,
    route="/t/[tenant_id]/dashboard",
    on_load=TenantState.load_tenant,
)

app.add_page(
    settings,
    route="/t/[tenant_id]/settings",
    on_load=TenantState.load_tenant,
)

# Seed tenants on startup
seed_tenants()
