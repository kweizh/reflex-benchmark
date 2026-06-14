import asyncio
import time
from typing import Optional, List
import reflex as rx
from .models import EmailDigest, SentEmail
from sqlmodel import select, func, delete
from fastapi import Request

SCHEDULER_TOKEN = "scheduler_session"

class State(rx.State):
    running: bool = False

    @rx.event(background=True)
    async def scheduler_loop(self):
        async with self:
            if self.running:
                return
            self.running = True
        
        try:
            while True:
                async with self:
                    if not self.running:
                        break
                
                now = time.time()
                with rx.session() as session:
                    statement = select(EmailDigest).where(EmailDigest.next_due_at <= now)
                    due_digests = session.exec(statement).all()
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
                    session.commit()
                
                await asyncio.sleep(1)
        finally:
            async with self:
                self.running = False

    @rx.event
    def force_run(self):
        now = time.time()
        with rx.session() as session:
            statement = select(EmailDigest).order_by(EmailDigest.next_due_at.asc()).limit(1)
            digest = session.exec(statement).first()
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

    @rx.event
    def stop_scheduler_event(self):
        self.running = False

    @rx.var
    def due_count(self) -> int:
        now = time.time()
        try:
            with rx.session() as session:
                return session.exec(select(func.count(EmailDigest.id)).where(EmailDigest.next_due_at <= now)).one()
        except:
            return 0

    @rx.var
    def queued_count(self) -> int:
        now = time.time()
        try:
            with rx.session() as session:
                return session.exec(select(func.count(EmailDigest.id)).where(EmailDigest.next_due_at > now)).one()
        except:
            return 0

    @rx.var
    def total_sent(self) -> int:
        try:
            with rx.session() as session:
                return session.exec(select(func.count(SentEmail.id))).one()
        except:
            return 0

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Email Scheduler"),
            rx.text(f"Running: {State.running}"),
            rx.text(f"Due: {State.due_count}"),
            rx.text(f"Queued: {State.queued_count}"),
            rx.text(f"Total Sent: {State.total_sent}"),
            rx.button("Force Run", on_click=State.force_run),
            rx.button("Start Scheduler", on_click=State.scheduler_loop),
            rx.button("Stop Scheduler", on_click=State.stop_scheduler_event),
            spacing="4",
        )
    )

def api_transformer(fastapi_app):
    @fastapi_app.post("/api/scheduler/seed")
    async def seed(request: Request):
        data = await request.json()
        digests = data.get("digests", [])
        now = time.time()
        with rx.session() as session:
            session.exec(delete(SentEmail))
            session.exec(delete(EmailDigest))
            count = 0
            for d in digests:
                new_digest = EmailDigest(
                    recipient=d["recipient"],
                    period_seconds=d["period_seconds"],
                    next_due_at=now + d["first_due_in_seconds"]
                )
                session.add(new_digest)
                count += 1
            session.commit()
        return {"seeded": count}

    @fastapi_app.post("/api/scheduler/start")
    async def start():
        state = await app.state_manager.get_state(SCHEDULER_TOKEN)
        asyncio.create_task(state.scheduler_loop())
        await asyncio.sleep(0.1)
        return {"running": True}

    @fastapi_app.post("/api/scheduler/stop")
    async def stop():
        state = await app.state_manager.get_state(SCHEDULER_TOKEN)
        async with state:
            state.running = False
        return {"running": False}

    @fastapi_app.post("/api/scheduler/force_run")
    async def force_run():
        state = await app.state_manager.get_state(SCHEDULER_TOKEN)
        state.force_run()
        # Find which one was just sent
        with rx.session() as session:
            # Get the most recent sent email
            statement = select(SentEmail).order_by(SentEmail.sent_at.desc()).limit(1)
            sent = session.exec(statement).first()
            if sent:
                return {"sent": 1, "digest_id": sent.digest_id, "recipient": sent.recipient}
        return {"sent": 0}

    @fastapi_app.get("/api/scheduler/status")
    async def status():
        state = await app.state_manager.get_state(SCHEDULER_TOKEN)
        now = time.time()
        with rx.session() as session:
            due_count = session.exec(select(func.count(EmailDigest.id)).where(EmailDigest.next_due_at <= now)).one()
            queued_count = session.exec(select(func.count(EmailDigest.id)).where(EmailDigest.next_due_at > now)).one()
            total_sent = session.exec(select(func.count(SentEmail.id))).one()
        
        return {
            "running": state.running,
            "now": now,
            "due_count": due_count,
            "queued_count": queued_count,
            "total_sent": total_sent
        }

    @fastapi_app.get("/api/scheduler/sent")
    async def sent():
        with rx.session() as session:
            rows = session.exec(select(SentEmail).order_by(SentEmail.sent_at.asc())).all()
            return {"rows": [{"id": r.id, "digest_id": r.digest_id, "recipient": r.recipient, "sent_at": r.sent_at} for r in rows]}

    return fastapi_app

app = rx.App(api_transformer=api_transformer)
app.add_page(index)
