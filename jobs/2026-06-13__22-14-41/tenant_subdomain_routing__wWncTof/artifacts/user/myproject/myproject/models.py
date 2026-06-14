"""Database models for the multi-tenant application."""

import reflex as rx
from sqlmodel import select


class Tenant(rx.Model, table=True):
    """A tenant in the multi-tenant application."""

    slug: str
    name: str


def seed_tenants():
    """Insert seed tenant rows if they do not already exist."""
    with rx.session() as session:
        try:
            existing = {t.slug for t in session.exec(select(Tenant)).all()}
        except Exception:
            # Table does not exist yet; skip seeding
            return
        tenants_to_add = [
            Tenant(slug="acme", name="Acme Corp"),
            Tenant(slug="globex", name="Globex Inc"),
            Tenant(slug="initech", name="Initech LLC"),
        ]
        for tenant in tenants_to_add:
            if tenant.slug not in existing:
                session.add(tenant)
        session.commit()
