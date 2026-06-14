import asyncio
import datetime
from typing import List, Dict

import reflex as rx
from sqlmodel import select, Field
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------
# Database Model
# ---------------------------------------------------------
class Job(rx.Model, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    status: str
    progress: int
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

# ---------------------------------------------------------
# State
# ---------------------------------------------------------
class AppState(rx.State):
    jobs: List[Job] = []
    
    _worker_started: bool = False
    new_job_name: str = ""

    def set_new_job_name(self, value: str):
        self.new_job_name = value

    @rx.var(cache=True)
    def status_counts(self) -> Dict[str, int]:
        counts = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for job in self.jobs:
            if job.status in counts:
                counts[job.status] += 1
            else:
                counts[job.status] = 1
        return counts

    def load_jobs(self):
        with rx.session() as session:
            self.jobs = session.exec(select(Job).order_by(Job.id)).all()

    def add_job(self):
        if not self.new_job_name:
            return
        with rx.session() as session:
            new_job = Job(name=self.new_job_name, status="PENDING", progress=0)
            session.add(new_job)
            session.commit()
            session.refresh(new_job)
        self.new_job_name = ""
        self.load_jobs()

    @rx.event(background=True)
    async def start_polling_worker(self):
        async with self:
            if AppState._worker_started:
                return
            AppState._worker_started = True

        while True:
            await asyncio.sleep(1.0)
            
            async with rx.asession() as session:
                pending_jobs = await session.exec(select(Job).where(Job.status == "PENDING").order_by(Job.id))
                job = pending_jobs.first()
            
            if not job:
                async with self:
                    with rx.session() as sync_session:
                        self.jobs = sync_session.exec(select(Job).order_by(Job.id)).all()
                continue
                
            for p in [20, 40, 60, 80, 100]:
                async with rx.asession() as session:
                    current_job = await session.get(Job, job.id)
                    if not current_job:
                        break
                    current_job.progress = p
                    if p < 100:
                        current_job.status = "RUNNING"
                    else:
                        current_job.status = "COMPLETED"
                    session.add(current_job)
                    await session.commit()
                
                async with self:
                    with rx.session() as sync_session:
                        self.jobs = sync_session.exec(select(Job).order_by(Job.id)).all()
                
                if p < 100:
                    await asyncio.sleep(0.2)

    def on_load(self):
        self.load_jobs()
        return AppState.start_polling_worker()


# ---------------------------------------------------------
# FastAPI Router
# ---------------------------------------------------------
from fastapi import FastAPI
fastapi_app = FastAPI()

class JobCreate(BaseModel):
    name: str

@fastapi_app.post("/jobs")
def create_job(job_data: JobCreate):
    if not job_data.name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    with rx.session() as session:
        new_job = Job(name=job_data.name, status="PENDING", progress=0)
        session.add(new_job)
        session.commit()
        session.refresh(new_job)
        return {"id": new_job.id, "name": new_job.name, "status": new_job.status, "progress": new_job.progress}

@fastapi_app.get("/jobs")
def get_jobs():
    with rx.session() as session:
        jobs = session.exec(select(Job).order_by(Job.id)).all()
        return [{"id": j.id, "name": j.name, "status": j.status, "progress": j.progress} for j in jobs]

@fastapi_app.get("/jobs/counts")
def get_job_counts():
    with rx.session() as session:
        jobs = session.exec(select(Job)).all()
        counts = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for j in jobs:
            if j.status in counts:
                counts[j.status] += 1
            else:
                counts[j.status] = 1
        return counts

def api_transformer(app):
    app.mount("/api", fastapi_app)
    return app

# ---------------------------------------------------------
# UI
# ---------------------------------------------------------
@rx.page(on_load=AppState.on_load)
def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Background Job Queue"),
            rx.hstack(
                rx.text("Pending: ", AppState.status_counts["PENDING"]),
                rx.text("Running: ", AppState.status_counts["RUNNING"]),
                rx.text("Completed: ", AppState.status_counts["COMPLETED"]),
            ),
            rx.hstack(
                rx.input(
                    placeholder="Job Name",
                    value=AppState.new_job_name,
                    on_change=AppState.set_new_job_name,
                ),
                rx.button(
                    "Submit",
                    on_click=AppState.add_job,
                ),
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("ID"),
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Status"),
                        rx.table.column_header_cell("Progress"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        AppState.jobs,
                        lambda job: rx.table.row(
                            rx.table.cell(job.id),
                            rx.table.cell(job.name),
                            rx.table.cell(job.status),
                            rx.table.cell(job.progress),
                        ),
                    )
                ),
            ),
            spacing="5",
        ),
    )

app = rx.App(api_transformer=api_transformer)
