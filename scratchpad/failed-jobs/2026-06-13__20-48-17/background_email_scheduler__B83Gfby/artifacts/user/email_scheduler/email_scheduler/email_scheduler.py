import reflex as rx
import time
import asyncio
from sqlmodel import select
from typing import Optional
from fastapi import Request

class EmailDigest(rx.Model, table=True):
    __tablename__ = "emaildigest"
    recipient: str
    period_seconds: int
    last_sent_at: Optional[float] = None
    next_due_at: float

class SentEmail(rx.Model, table=True):
    __tablename__ = "sentemail"
    digest_id: int
    recipient: str
    sent_at: float

class State(rx.State):
    due_count: int = 0
    queued_count: int = 0
    total_sent: int = 0
    
    _is_running: bool = False

    @rx.event(background=True)
    async def scheduler_loop(self):
        while self._is_running:
            now = time.time()
            with rx.session() as session:
                due_digests = session.exec(
                    select(EmailDigest).where(EmailDigest.next_due_at <= now)
                ).all()

                for digest in due_digests:
                    sent = SentEmail(
                        digest_id=digest.id,
                        recipient=digest.recipient,
                        sent_at=now
                    )
                    session.add(sent)
                    
                    digest.last_sent_at = now
                    digest.next_due_at = now + digest.period_seconds
                    session.add(digest)
                
                if due_digests:
                    session.commit()
            
            async with self:
                now = time.time()
                with rx.session() as session:
                    self.due_count = len(session.exec(select(EmailDigest).where(EmailDigest.next_due_at <= now)).all())
                    self.queued_count = len(session.exec(select(EmailDigest).where(EmailDigest.next_due_at > now)).all())
                    self.total_sent = len(session.exec(select(SentEmail)).all())
            
            await asyncio.sleep(1)

    @rx.event
    def force_run(self):
        now = time.time()
        with rx.session() as session:
            digest = session.exec(
                select(EmailDigest).order_by(EmailDigest.next_due_at.asc()).limit(1)
            ).first()
            if digest:
                sent = SentEmail(
                    digest_id=digest.id,
                    recipient=digest.recipient,
                    sent_at=now
                )
                session.add(sent)
                digest.last_sent_at = now
                digest.next_due_at = now + digest.period_seconds
                session.add(digest)
                session.commit()

        # Update UI state
        with rx.session() as session:
            self.due_count = len(session.exec(select(EmailDigest).where(EmailDigest.next_due_at <= now)).all())
            self.queued_count = len(session.exec(select(EmailDigest).where(EmailDigest.next_due_at > now)).all())
            self.total_sent = len(session.exec(select(SentEmail)).all())


class DummyState:
    def __init__(self):
        self.due_count = 0
        self.queued_count = 0
        self.total_sent = 0
        self._is_running = False
    async def __aenter__(self):
        pass
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

_dummy_state = DummyState()
_scheduler_task = None

async def api_seed(request: Request):
    data = await request.json()
    now = time.time()
    with rx.session() as session:
        for d in session.exec(select(EmailDigest)).all():
            session.delete(d)
        for s in session.exec(select(SentEmail)).all():
            session.delete(s)
            
        count = 0
        for d in data.get("digests", []):
            digest = EmailDigest(
                recipient=d["recipient"],
                period_seconds=d["period_seconds"],
                last_sent_at=None,
                next_due_at=now + d["first_due_in_seconds"]
            )
            session.add(digest)
            count += 1
        session.commit()
    return {"seeded": count}

async def api_start():
    global _scheduler_task, _dummy_state
    if not _dummy_state._is_running:
        _dummy_state._is_running = True
        _scheduler_task = asyncio.create_task(State.scheduler_loop.fn(_dummy_state))
    return {"running": True}

async def api_stop():
    global _dummy_state
    _dummy_state._is_running = False
    return {"running": False}

async def api_force_run():
    now = time.time()
    sent_info = None
    with rx.session() as session:
        digest = session.exec(
            select(EmailDigest).order_by(EmailDigest.next_due_at.asc()).limit(1)
        ).first()
        if digest:
            sent = SentEmail(
                digest_id=digest.id,
                recipient=digest.recipient,
                sent_at=now
            )
            session.add(sent)
            digest.last_sent_at = now
            digest.next_due_at = now + digest.period_seconds
            session.add(digest)
            session.commit()
            session.refresh(sent)
            sent_info = {
                "sent": 1,
                "digest_id": sent.digest_id,
                "recipient": sent.recipient
            }
    
    if sent_info:
        return sent_info
    return {"sent": 0}

async def api_status():
    global _dummy_state
    now = time.time()
    with rx.session() as session:
        due_count = len(session.exec(select(EmailDigest).where(EmailDigest.next_due_at <= now)).all())
        queued_count = len(session.exec(select(EmailDigest).where(EmailDigest.next_due_at > now)).all())
        total_sent = len(session.exec(select(SentEmail)).all())
        
    return {
        "running": _dummy_state._is_running,
        "now": now,
        "due_count": due_count,
        "queued_count": queued_count,
        "total_sent": total_sent
    }

async def api_sent():
    with rx.session() as session:
        rows = session.exec(select(SentEmail).order_by(SentEmail.sent_at.asc())).all()
        return {
            "rows": [
                {
                    "id": r.id,
                    "digest_id": r.digest_id,
                    "recipient": r.recipient,
                    "sent_at": r.sent_at
                } for r in rows
            ]
        }

def api_transformer(fastapi_app):
    fastapi_app.add_api_route("/api/scheduler/seed", api_seed, methods=["POST"])
    fastapi_app.add_api_route("/api/scheduler/start", api_start, methods=["POST"])
    fastapi_app.add_api_route("/api/scheduler/stop", api_stop, methods=["POST"])
    fastapi_app.add_api_route("/api/scheduler/force_run", api_force_run, methods=["POST"])
    fastapi_app.add_api_route("/api/scheduler/status", api_status, methods=["GET"])
    fastapi_app.add_api_route("/api/scheduler/sent", api_sent, methods=["GET"])
    return fastapi_app

def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Email Scheduler"),
        rx.text(f"Due count: {State.due_count}"),
        rx.text(f"Queued count: {State.queued_count}"),
        rx.text(f"Total sent: {State.total_sent}"),
        rx.button("Force Run", on_click=State.force_run),
    )

app = rx.App(api_transformer=api_transformer)
app.add_page(index)
