import reflex as rx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import sqlite3
import os

# Model
class Tenant(rx.Model, table=True):
    slug: str
    name: str

# State
class State(rx.State):
    tenant_name: str = ""
    tenant_exists: bool = False

    @rx.event
    def get_tenant(self):
        tenant_id = self.router.page.params.get("tenant_id")
        with rx.session() as session:
            tenant = session.exec(
                Tenant.select().where(Tenant.slug == tenant_id)
            ).first()
            if tenant:
                self.tenant_name = tenant.name
                self.tenant_exists = True
            else:
                self.tenant_name = ""
                self.tenant_exists = False

# Seed function
def seed_db():
    tenants = [
        ("acme", "Acme Corp"),
        ("globex", "Globex Inc"),
        ("initech", "Initech LLC"),
    ]
    try:
        with rx.session() as session:
            for slug, name in tenants:
                existing = session.exec(Tenant.select().where(Tenant.slug == slug)).first()
                if not existing:
                    session.add(Tenant(slug=slug, name=name))
            session.commit()
    except Exception:
        pass

# Pages
def dashboard():
    return rx.vstack(
        rx.cond(
            State.tenant_exists,
            rx.fragment(
                rx.text(State.tenant_name),
                rx.text("Dashboard"),
            ),
            rx.text("Tenant Not Found"),
        )
    )

def settings():
    return rx.vstack(
        rx.cond(
            State.tenant_exists,
            rx.fragment(
                rx.text(State.tenant_name),
                rx.text("Settings"),
            ),
            rx.text("Tenant Not Found"),
        )
    )

# FastAPI Middleware
class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            tenant_id = request.headers.get("X-Tenant-Id")
            if not tenant_id:
                return JSONResponse(status_code=403, content={"detail": "forbidden"})
            
            project_dir = "/home/user/myproject"
            db_path = os.path.join(project_dir, "reflex.db")
            if not os.path.exists(db_path):
                return JSONResponse(status_code=403, content={"detail": "forbidden"})
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT name FROM tenant WHERE slug = ?", (tenant_id,))
                row = cursor.fetchone()
            except sqlite3.OperationalError:
                row = None
            finally:
                conn.close()
            
            if not row:
                return JSONResponse(status_code=403, content={"detail": "forbidden"})
            
            request.state.tenant_slug = tenant_id
            request.state.tenant_name = row[0]
            
        return await call_next(request)

def api_transformer(app):
    app.add_middleware(TenantMiddleware)
    
    async def me(request: Request):
        return JSONResponse({
            "slug": getattr(request.state, "tenant_slug", None),
            "name": getattr(request.state, "tenant_name", None)
        })
    
    app.add_route("/api/me", me, methods=["GET"])
    return app

app = rx.App(api_transformer=api_transformer)
app.add_page(dashboard, route="/t/[tenant_id]/dashboard", on_load=State.get_tenant)
app.add_page(settings, route="/t/[tenant_id]/settings", on_load=State.get_tenant)

# Seed the database
seed_db()
