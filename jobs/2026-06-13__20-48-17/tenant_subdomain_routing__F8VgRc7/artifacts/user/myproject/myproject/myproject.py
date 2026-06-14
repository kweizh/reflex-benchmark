import reflex as rx
from sqlmodel import select
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class Tenant(rx.Model, table=True):
    slug: str
    name: str

class TenantState(rx.State):
    tenant_name: str = ""
    tenant_found: bool = False

    def check_tenant(self):
        tenant_id = self.router.page.params.get("tenant_id", "")
        with rx.session() as session:
            tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_id)).first()
            if tenant:
                self.tenant_name = tenant.name
                self.tenant_found = True
            else:
                self.tenant_name = ""
                self.tenant_found = False

def dashboard_page() -> rx.Component:
    return rx.cond(
        TenantState.tenant_found,
        rx.vstack(
            rx.text(TenantState.tenant_name),
            rx.text("Dashboard")
        ),
        rx.text("Tenant Not Found")
    )

def settings_page() -> rx.Component:
    return rx.cond(
        TenantState.tenant_found,
        rx.vstack(
            rx.text(TenantState.tenant_name),
            rx.text("Settings")
        ),
        rx.text("Tenant Not Found")
    )

def api_transformer(reflex_app):
    fastapi_app = FastAPI()

    @fastapi_app.middleware("http")
    async def tenant_middleware(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            tenant_id = request.headers.get("X-Tenant-Id")
            if not tenant_id:
                return JSONResponse(status_code=403, content={"detail": "forbidden"})
            
            with rx.session() as session:
                tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_id)).first()
                if not tenant:
                    return JSONResponse(status_code=403, content={"detail": "forbidden"})
                
                request.state.tenant = tenant
                
        response = await call_next(request)
        return response

    @fastapi_app.get("/api/me")
    def get_me(request: Request):
        tenant = request.state.tenant
        return {"slug": tenant.slug, "name": tenant.name}

    fastapi_app.mount("/", reflex_app)
    return fastapi_app

app = rx.App(api_transformer=api_transformer)
app.add_page(dashboard_page, route="/t/[tenant_id]/dashboard", on_load=TenantState.check_tenant)
app.add_page(settings_page, route="/t/[tenant_id]/settings", on_load=TenantState.check_tenant)

def seed_db():
    with rx.session() as session:
        tenants = [
            ("acme", "Acme Corp"),
            ("globex", "Globex Inc"),
            ("initech", "Initech LLC")
        ]
        for slug, name in tenants:
            if not session.exec(select(Tenant).where(Tenant.slug == slug)).first():
                session.add(Tenant(slug=slug, name=name))
        session.commit()

app.register_lifespan_task(seed_db)
