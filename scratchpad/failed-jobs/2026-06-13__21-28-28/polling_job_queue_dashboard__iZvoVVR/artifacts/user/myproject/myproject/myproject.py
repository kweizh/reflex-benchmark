"""Background polling job queue dashboard built with Reflex."""

import asyncio
import datetime
from typing import Any

import reflex as rx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import select


# ---------------------------------------------------------------------------
# SQL Model
# ---------------------------------------------------------------------------

class Job(rx.Model, table=True):
    """A queued job that is processed by the background worker."""

    name: str = ""
    status: str = "PENDING"
    progress: int = 0
    created_at: datetime.datetime = datetime.datetime.utcnow()


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------

class State(rx.State):
    """Application state holding the in-memory job list and background worker."""

    jobs: list[Job] = []
    new_job_name: str = ""
    _worker_started: bool = False

    # -- cached computed var for status counts --
    @rx.var(cache=True)
    def status_counts(self) -> dict[str, int]:
        """Return per-status counts derived from the in-memory job list."""
        counts: dict[str, int] = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for job in self.jobs:
            if job.status in counts:
                counts[job.status] += 1
        return counts

    @rx.event
    def set_new_job_name(self, value: str) -> None:
        """Setter for the job name input."""
        self.new_job_name = value

    # -- submit action from UI --
    @rx.event
    async def submit_job(self) -> None:
        """Insert a new PENDING job into the database and refresh state."""
        name = self.new_job_name.strip()
        if not name:
            return
        async with rx.asession() as session:
            job = Job(name=name, status="PENDING", progress=0, created_at=datetime.datetime.utcnow())
            session.add(job)
            await session.commit()
            await session.refresh(job)
        self.new_job_name = ""
        await self._refresh_jobs()

    # -- background polling worker --
    @rx.event(background=True)
    async def poll_jobs(self) -> None:
        """Indefinite loop: claim oldest PENDING job and advance it to COMPLETED."""
        # Guard against duplicate workers
        async with self:
            if self._worker_started:
                return
            self._worker_started = True  # type: ignore[assignment]

        progress_steps = [20, 40, 60, 80, 100]

        while True:
            await asyncio.sleep(1)

            # --- DB I/O outside the state lock ---
            async with rx.asession() as session:
                # Find the oldest PENDING job
                result = await session.execute(
                    select(Job).where(Job.status == "PENDING").order_by(Job.id).limit(1)
                )
                job_row = result.scalar_one_or_none()

                if job_row is None:
                    continue

                job_id = job_row.id

                # Claim the job: set status to RUNNING
                job_row.status = "RUNNING"
                session.add(job_row)
                await session.commit()
                await session.refresh(job_row)

            # Advance through progress steps
            for step in progress_steps:
                # Small sleep between steps so progress is observable
                await asyncio.sleep(1)

                async with rx.asession() as session:
                    result = await session.execute(
                        select(Job).where(Job.id == job_id)
                    )
                    job_row = result.scalar_one_or_none()
                    if job_row is None:
                        break

                    job_row.progress = step
                    if step == 100:
                        job_row.status = "COMPLETED"
                    else:
                        job_row.status = "RUNNING"
                    session.add(job_row)
                    await session.commit()

            # --- Update Reflex state inside async with self ---
            async with self:
                await self._refresh_jobs()

    async def _refresh_jobs(self) -> None:
        """Re-fetch all jobs from DB and update the in-memory list."""
        async with rx.asession() as session:
            result = await session.execute(select(Job).order_by(Job.id))
            rows = result.scalars().all()
            # Convert to list of Job objects to avoid detached-instance issues
            self.jobs = [
                Job(
                    id=r.id,
                    name=r.name,
                    status=r.status,
                    progress=r.progress,
                    created_at=r.created_at,
                )
                for r in rows
            ]


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------

api_app = FastAPI()


class JobCreateRequest(BaseModel):
    name: str


@api_app.post("/api/jobs")
async def create_job(body: JobCreateRequest) -> JSONResponse:
    """Enqueue a new PENDING job."""
    name = body.name.strip()
    if not name:
        return JSONResponse(
            status_code=400,
            content={"error": "name must be a non-empty string"},
        )
    async with rx.asession() as session:
        job = Job(name=name, status="PENDING", progress=0, created_at=datetime.datetime.utcnow())
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return JSONResponse(
            status_code=201,
            content={
                "id": job.id,
                "name": job.name,
                "status": job.status,
                "progress": job.progress,
            },
        )


@api_app.get("/api/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    """List all jobs sorted by id ascending."""
    async with rx.asession() as session:
        result = await session.execute(select(Job).order_by(Job.id))
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "status": r.status,
                "progress": r.progress,
            }
            for r in rows
        ]


@api_app.get("/api/jobs/counts")
async def job_counts() -> dict[str, int]:
    """Return per-status counts from the database."""
    async with rx.asession() as session:
        result = await session.execute(select(Job))
        rows = result.scalars().all()
        counts: dict[str, int] = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for r in rows:
            if r.status in counts:
                counts[r.status] += 1
        return counts


# ---------------------------------------------------------------------------
# Reflex UI
# ---------------------------------------------------------------------------

def index() -> rx.Component:
    """The index page with submit form, status summary, and job table."""
    return rx.container(
        rx.vstack(
            rx.heading("Job Queue Dashboard", size="8"),
            # Submit form
            rx.hstack(
                rx.input(
                    placeholder="Job name",
                    value=State.new_job_name,
                    on_change=State.set_new_job_name,
                ),
                rx.button("Submit", on_click=State.submit_job),
                spacing="3",
            ),
            # Status-count summary
            rx.box(
                rx.hstack(
                    rx.text("PENDING: "),
                    rx.text(State.status_counts["PENDING"]),
                    rx.text(" | RUNNING: "),
                    rx.text(State.status_counts["RUNNING"]),
                    rx.text(" | COMPLETED: "),
                    rx.text(State.status_counts["COMPLETED"]),
                    spacing="2",
                ),
                margin_y="1em",
            ),
            # Job table
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("ID"),
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Status"),
                        rx.table.column_header_cell("Progress"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        State.jobs,
                        lambda job: rx.table.row(
                            rx.table.cell(job.id),
                            rx.table.cell(job.name),
                            rx.table.cell(job.status),
                            rx.table.cell(str(job.progress)),
                        ),
                    ),
                ),
            ),
            spacing="4",
            align="stretch",
        ),
        on_mount=State.poll_jobs,
    )


app = rx.App(api_transformer=api_app)
app.add_page(index)