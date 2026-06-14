"""Job Queue Dashboard - Reflex application with background polling worker."""

import asyncio
import datetime
from typing import Any

import reflex as rx
from sqlmodel import select, func

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ──────────────────────────────────────────────────────────────────────────────
# SQL Model
# ──────────────────────────────────────────────────────────────────────────────

class Job(rx.Model, table=True):
    """A job in the processing queue."""
    name: str
    status: str = "PENDING"
    progress: int = 0
    created_at: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI Schemas
# ──────────────────────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    name: str


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI Router (mounted via api_transformer)
# ──────────────────────────────────────────────────────────────────────────────

api_app = FastAPI()


@api_app.post("/api/jobs")
async def api_create_job(request: JobCreateRequest):
    """Enqueue a new PENDING job."""
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="name must be a non-empty string")
    async with rx.asession() as session:
        job = Job(
            name=request.name.strip(),
            status="PENDING",
            progress=0,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
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
async def api_list_jobs():
    """List all jobs, sorted by id ascending."""
    async with rx.asession() as session:
        result = await session.execute(
            select(Job).order_by(Job.id.asc())
        )
        jobs = result.scalars().all()
        return [
            {
                "id": j.id,
                "name": j.name,
                "status": j.status,
                "progress": j.progress,
            }
            for j in jobs
        ]


@api_app.get("/api/jobs/counts")
async def api_job_counts():
    """Return per-status counts derived from the database."""
    async with rx.asession() as session:
        result = await session.execute(
            select(Job.status, func.count(Job.id)).group_by(Job.status)
        )
        rows = result.all()
        counts = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for status, count in rows:
            if status in counts:
                counts[status] = count
        return counts


# ──────────────────────────────────────────────────────────────────────────────
# Reflex State
# ──────────────────────────────────────────────────────────────────────────────

class State(rx.State):
    """Application state with job list and background polling."""

    jobs: list[dict[str, Any]] = []

    # Guard to prevent duplicate polling workers
    _polling_started: bool = False

    async def _fetch_jobs(self) -> list[dict[str, Any]]:
        """Fetch all jobs from the database, sorted by id."""
        async with rx.asession() as session:
            result = await session.execute(
                select(Job).order_by(Job.id.asc())
            )
            rows = result.scalars().all()
            return [
                {"id": r.id, "name": r.name, "status": r.status, "progress": r.progress}
                for r in rows
            ]

    @rx.event
    async def submit_job(self, form_data: dict[str, Any]):
        """Handle job submission from the UI form."""
        name = (form_data.get("name") or "").strip()
        if not name:
            return
        async with rx.asession() as session:
            job = Job(
                name=name,
                status="PENDING",
                progress=0,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(job)
            await session.commit()
        # Refresh the job list in state
        jobs = await self._fetch_jobs()
        async with self:
            self.jobs = jobs
            # Clear the input by resetting the form field
            self.reset()

    @rx.event(background=True)
    async def start_polling(self):
        """Background polling worker: claims PENDING jobs and processes them."""
        # Guard against duplicate workers
        if State._polling_started:
            return
        State._polling_started = True

        try:
            while True:
                await asyncio.sleep(1)

                # Claim the oldest PENDING job (lowest id) — DB I/O outside state lock
                claimed_job = None
                async with rx.asession() as session:
                    result = await session.execute(
                        select(Job)
                        .where(Job.status == "PENDING")
                        .order_by(Job.id.asc())
                        .limit(1)
                    )
                    job = result.scalars().first()
                    if job is not None:
                        job.status = "RUNNING"
                        job.progress = 0
                        session.add(job)
                        await session.commit()
                        await session.refresh(job)
                        claimed_job = {
                            "id": job.id,
                            "name": job.name,
                            "status": job.status,
                            "progress": job.progress,
                        }

                if claimed_job is None:
                    # No pending jobs — just refresh the list and wait
                    jobs = await self._fetch_jobs()
                    async with self:
                        self.jobs = jobs
                    continue

                # Process the claimed job through 5 progress steps: 20 -> 40 -> 60 -> 80 -> 100
                progress_steps = [20, 40, 60, 80, 100]
                for step in progress_steps:
                    await asyncio.sleep(1)
                    async with rx.asession() as session:
                        result = await session.execute(
                            select(Job).where(Job.id == claimed_job["id"])
                        )
                        db_job = result.scalars().first()
                        if db_job is None:
                            break
                        db_job.progress = step
                        if step < 100:
                            db_job.status = "RUNNING"
                        else:
                            db_job.status = "COMPLETED"
                        session.add(db_job)
                        await session.commit()

                # After processing, refresh the job list in state
                jobs = await self._fetch_jobs()
                async with self:
                    self.jobs = jobs

        except asyncio.CancelledError:
            pass

    @rx.var(cache=True)
    def job_counts(self) -> dict[str, int]:
        """Cached computed var: per-status counts from the in-memory job list."""
        counts = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for job in self.jobs:
            status = job.get("status", "")
            if status in counts:
                counts[status] += 1
        return counts


# ──────────────────────────────────────────────────────────────────────────────
# UI Components
# ──────────────────────────────────────────────────────────────────────────────

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Job Queue Dashboard", size="8"),
            # Submit form
            rx.form(
                rx.hstack(
                    rx.input(
                        name="name",
                        placeholder="Enter job name...",
                        width="300px",
                    ),
                    rx.button("Submit Job", type="submit"),
                ),
                on_submit=State.submit_job,
                reset_on_submit=True,
            ),
            # Status count summary
            rx.hstack(
                rx.text("Status Summary:", font_weight="bold"),
                rx.text(
                    "PENDING: ",
                    State.job_counts["PENDING"],
                    "  RUNNING: ",
                    State.job_counts["RUNNING"],
                    "  COMPLETED: ",
                    State.job_counts["COMPLETED"],
                ),
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
                            rx.table.cell(job["id"]),
                            rx.table.cell(job["name"]),
                            rx.table.cell(job["status"]),
                            rx.table.cell(f"{job['progress']}%"),
                        ),
                    ),
                ),
            ),
            spacing="5",
            align="start",
            padding="2em",
        ),
        # Trigger the background polling on page load
        on_mount=State.start_polling,
    )


# ──────────────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────────────

app = rx.App(
    api_transformer=lambda app: app.mount("/", api_app),
)
app.add_page(index, route="/")
