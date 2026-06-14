"""Email Scheduler - A Reflex application with background scheduler loop."""

import asyncio
import time
from typing import Optional

import reflex as rx
from sqlmodel import select
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class EmailDigest(rx.Model, table=True):
    """Table of scheduled email digests."""

    recipient: str
    period_seconds: int
    last_sent_at: Optional[float] = None
    next_due_at: float


class SentEmail(rx.Model, table=True):
    """Audit table of sent emails."""

    digest_id: int
    recipient: str
    sent_at: float


# ---------------------------------------------------------------------------
# Global scheduler state (module-level so API handlers and state share it)
# ---------------------------------------------------------------------------

_scheduler_running: bool = False
_scheduler_task: Optional[asyncio.Task] = None


async def _scheduler_coroutine() -> None:
    """Core scheduler loop that runs as a standalone asyncio task."""
    global _scheduler_running
    while _scheduler_running:
        await asyncio.sleep(1)
        now = time.time()
        try:
            with rx.session() as session:
                due_digests = session.exec(
                    select(EmailDigest).where(EmailDigest.next_due_at <= now)
                ).all()
                for digest in due_digests:
                    sent = SentEmail(
                        digest_id=digest.id,
                        recipient=digest.recipient,
                        sent_at=now,
                    )
                    session.add(sent)
                    digest.last_sent_at = now
                    digest.next_due_at = now + digest.period_seconds
                    session.add(digest)
                session.commit()
        except Exception:
            pass  # Keep the loop alive even if a tick fails


def _start_scheduler_loop() -> None:
    """Start the scheduler coroutine if it is not already running."""
    global _scheduler_running, _scheduler_task
    if not _scheduler_running:
        _scheduler_running = True
        _scheduler_task = asyncio.create_task(_scheduler_coroutine())


def _stop_scheduler_loop() -> None:
    """Signal the scheduler coroutine to stop and cancel the task."""
    global _scheduler_running, _scheduler_task
    _scheduler_running = False
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------

class SchedulerState(rx.State):
    """State for the scheduler UI and background event."""

    running: bool = False
    due_count: int = 0
    queued_count: int = 0
    total_sent: int = 0

    # ----- background scheduler event (required by spec) -------------------

    @rx.event(background=True)
    async def scheduler_loop(self) -> None:
        """Background event: tick every ~1 s and process due digests."""
        global _scheduler_running
        _scheduler_running = True
        while _scheduler_running:
            await asyncio.sleep(1)
            now = time.time()
            try:
                with rx.session() as session:
                    due_digests = session.exec(
                        select(EmailDigest).where(
                            EmailDigest.next_due_at <= now
                        )
                    ).all()
                    for digest in due_digests:
                        sent = SentEmail(
                            digest_id=digest.id,
                            recipient=digest.recipient,
                            sent_at=now,
                        )
                        session.add(sent)
                        digest.last_sent_at = now
                        digest.next_due_at = now + digest.period_seconds
                        session.add(digest)
                    session.commit()
            except Exception:
                pass

            # Update shared state vars inside the lock
            async with self:
                try:
                    now2 = time.time()
                    with rx.session() as s2:
                        self.due_count = len(
                            s2.exec(
                                select(EmailDigest).where(
                                    EmailDigest.next_due_at <= now2
                                )
                            ).all()
                        )
                        self.queued_count = len(
                            s2.exec(
                                select(EmailDigest).where(
                                    EmailDigest.next_due_at > now2
                                )
                            ).all()
                        )
                        self.total_sent = len(
                            s2.exec(select(SentEmail)).all()
                        )
                except Exception:
                    pass
                self.running = True

        async with self:
            self.running = False

    # ----- UI event handlers -----------------------------------------------

    @rx.event
    def start_scheduler(self) -> list:
        """Start the background scheduler from the UI."""
        global _scheduler_running
        if not _scheduler_running:
            self.running = True
            return [self.scheduler_loop()]
        return []

    @rx.event
    def stop_scheduler(self) -> None:
        """Stop the background scheduler from the UI."""
        global _scheduler_running
        _scheduler_running = False
        self.running = False

    @rx.event
    def force_run(self) -> None:
        """Force-send the earliest digest regardless of due status."""
        with rx.session() as session:
            digest = session.exec(
                select(EmailDigest).order_by(EmailDigest.next_due_at)
            ).first()
            if digest is not None:
                now = time.time()
                sent = SentEmail(
                    digest_id=digest.id,
                    recipient=digest.recipient,
                    sent_at=now,
                )
                session.add(sent)
                digest.last_sent_at = now
                digest.next_due_at = now + digest.period_seconds
                session.add(digest)
                session.commit()


# ---------------------------------------------------------------------------
# HTTP API handlers (Starlette routes)
# ---------------------------------------------------------------------------

async def api_seed(request: Request) -> JSONResponse:
    """POST /api/scheduler/seed – wipe and re-seed digest table."""
    body = await request.json()
    digests = body.get("digests", [])

    with rx.session() as session:
        # Wipe sent emails first (FK safety)
        for row in session.exec(select(SentEmail)):
            session.delete(row)
        for row in session.exec(select(EmailDigest)):
            session.delete(row)
        session.commit()

        now = time.time()
        for d in digests:
            digest = EmailDigest(
                recipient=d["recipient"],
                period_seconds=d["period_seconds"],
                last_sent_at=None,
                next_due_at=now + d["first_due_in_seconds"],
            )
            session.add(digest)
        session.commit()

    return JSONResponse({"seeded": len(digests)})


async def api_start(request: Request) -> JSONResponse:
    """POST /api/scheduler/start – ensure the scheduler loop is running."""
    _start_scheduler_loop()
    return JSONResponse({"running": True})


async def api_stop(request: Request) -> JSONResponse:
    """POST /api/scheduler/stop – signal the scheduler loop to exit."""
    _stop_scheduler_loop()
    return JSONResponse({"running": False})


async def api_force_run(request: Request) -> JSONResponse:
    """POST /api/scheduler/force_run – send the earliest digest immediately."""
    with rx.session() as session:
        digest = session.exec(
            select(EmailDigest).order_by(EmailDigest.next_due_at)
        ).first()
        if digest is None:
            return JSONResponse({"sent": 0, "digest_id": 0, "recipient": ""})

        now = time.time()
        sent = SentEmail(
            digest_id=digest.id,
            recipient=digest.recipient,
            sent_at=now,
        )
        session.add(sent)
        digest.last_sent_at = now
        digest.next_due_at = now + digest.period_seconds
        session.add(digest)
        session.commit()

        return JSONResponse(
            {"sent": 1, "digest_id": digest.id, "recipient": digest.recipient}
        )


async def api_status(request: Request) -> JSONResponse:
    """GET /api/scheduler/status – current scheduler status."""
    now = time.time()
    with rx.session() as session:
        due_count = len(
            session.exec(
                select(EmailDigest).where(EmailDigest.next_due_at <= now)
            ).all()
        )
        queued_count = len(
            session.exec(
                select(EmailDigest).where(EmailDigest.next_due_at > now)
            ).all()
        )
        total_sent = len(session.exec(select(SentEmail)).all())

    return JSONResponse(
        {
            "running": _scheduler_running,
            "now": now,
            "due_count": due_count,
            "queued_count": queued_count,
            "total_sent": total_sent,
        }
    )


async def api_sent(request: Request) -> JSONResponse:
    """GET /api/scheduler/sent – list all sent emails ordered by sent_at."""
    with rx.session() as session:
        rows = session.exec(
            select(SentEmail).order_by(SentEmail.sent_at)
        ).all()
        result = [
            {
                "id": r.id,
                "digest_id": r.digest_id,
                "recipient": r.recipient,
                "sent_at": r.sent_at,
            }
            for r in rows
        ]

    return JSONResponse({"rows": result})


# ---------------------------------------------------------------------------
# Starlette sub-app that hosts the /api/scheduler/* routes
# ---------------------------------------------------------------------------

api_app = Starlette(
    routes=[
        Route("/scheduler/seed", api_seed, methods=["POST"]),
        Route("/scheduler/start", api_start, methods=["POST"]),
        Route("/scheduler/stop", api_stop, methods=["POST"]),
        Route("/scheduler/force_run", api_force_run, methods=["POST"]),
        Route("/scheduler/status", api_status, methods=["GET"]),
        Route("/scheduler/sent", api_sent, methods=["GET"]),
    ],
)


# ---------------------------------------------------------------------------
# Reflex UI (minimal page + state wiring)
# ---------------------------------------------------------------------------

def index() -> rx.Component:
    """Main page showing scheduler status and controls."""
    return rx.container(
        rx.vstack(
            rx.heading("Email Digest Scheduler", size="8"),
            rx.hstack(
                rx.text("Running: "),
                rx.text(SchedulerState.running),
            ),
            rx.hstack(
                rx.text("Due: "),
                rx.text(SchedulerState.due_count),
            ),
            rx.hstack(
                rx.text("Queued: "),
                rx.text(SchedulerState.queued_count),
            ),
            rx.hstack(
                rx.text("Total Sent: "),
                rx.text(SchedulerState.total_sent),
            ),
            rx.hstack(
                rx.button("Start", on_click=SchedulerState.start_scheduler),
                rx.button("Stop", on_click=SchedulerState.stop_scheduler),
                rx.button("Force Run", on_click=SchedulerState.force_run),
            ),
            spacing="4",
            align="center",
            justify="center",
            min_height="85vh",
        ),
    )


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = rx.App(api_transformer=api_app)
app.add_page(index)