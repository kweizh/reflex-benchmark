import reflex as rx
from datetime import datetime
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, APIRouter
from sqlmodel import select

class Job(rx.Model, table=True):
    name: str
    status: str = "PENDING"
    progress: int = 0
    created_at: datetime = datetime.utcnow()

class State(rx.State):
    jobs: List[Job] = []
    _worker_running: bool = False
    new_job_name: str = ""

    def set_new_job_name(self, name: str):
        self.new_job_name = name

    @rx.var(cache=True)
    def counts(self) -> Dict[str, int]:
        c = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for job in self.jobs:
            if job.status in c:
                c[job.status] += 1
        return c

    async def load_jobs(self):
        async with rx.asession() as session:
            statement = select(Job).order_by(Job.id)
            results = await session.exec(statement)
            self.jobs = results.all()

    async def submit_job(self):
        if not self.new_job_name or not self.new_job_name.strip():
            return
        async with rx.asession() as session:
            job = Job(name=self.new_job_name, status="PENDING", progress=0, created_at=datetime.utcnow())
            session.add(job)
            await session.commit()
        self.new_job_name = ""
        await self.load_jobs()

    @rx.event(background=True)
    async def polling_worker(self):
        async with self:
            if self._worker_running:
                return
            self._worker_running = True
            await self.load_jobs()

        while True:
            try:
                async with rx.asession() as session:
                    # Claim oldest PENDING job
                    statement = select(Job).where(Job.status == "PENDING").order_by(Job.id)
                    results = await session.exec(statement)
                    job = results.first()
                    
                    if job:
                        # Transition to RUNNING
                        job.status = "RUNNING"
                        job.progress = 0
                        session.add(job)
                        await session.commit()
                        await session.refresh(job)
                        
                        async with self:
                            await self.load_jobs()

                        # Progress sequence: 20 -> 40 -> 60 -> 80 -> 100
                        for p in [20, 40, 60, 80, 100]:
                            await asyncio.sleep(1)
                            job.progress = p
                            if p == 100:
                                job.status = "COMPLETED"
                            else:
                                job.status = "RUNNING"
                            session.add(job)
                            await session.commit()
                            await session.refresh(job)
                            
                            async with self:
                                await self.load_jobs()
                    else:
                        # No jobs, sleep a bit
                        pass
                
                # Re-fetch just in case external changes happened
                async with self:
                    await self.load_jobs()
            except Exception as e:
                # Log error or handle it
                pass
            
            await asyncio.sleep(1)

router = APIRouter()

@router.post("/api/jobs")
async def create_job_api(job_data: Dict[str, str]):
    name = job_data.get("name")
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    async with rx.asession() as session:
        job = Job(name=name, status="PENDING", progress=0, created_at=datetime.utcnow())
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return {"id": job.id, "name": job.name, "status": job.status, "progress": job.progress}

@router.get("/api/jobs")
async def list_jobs_api():
    async with rx.asession() as session:
        statement = select(Job).order_by(Job.id)
        results = await session.exec(statement)
        jobs = results.all()
        return [{"id": j.id, "name": j.name, "status": j.status, "progress": j.progress} for j in jobs]

@router.get("/api/jobs/counts")
async def job_counts_api():
    async with rx.asession() as session:
        statement = select(Job)
        results = await session.exec(statement)
        jobs = results.all()
        counts = {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0}
        for j in jobs:
            if j.status in counts:
                counts[j.status] += 1
        return counts

def api_transformer(app: FastAPI) -> FastAPI:
    app.include_router(router)
    return app

def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Job Queue Dashboard", size="9"),
        rx.hstack(
            rx.input(
                placeholder="Job Name",
                value=State.new_job_name,
                on_change=State.set_new_job_name,
            ),
            rx.button("Submit", on_click=State.submit_job),
        ),
        rx.hstack(
            rx.text(f"PENDING: {State.counts['PENDING']}"),
            rx.text(f"RUNNING: {State.counts['RUNNING']}"),
            rx.text(f"COMPLETED: {State.counts['COMPLETED']}"),
            spacing="4",
        ),
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
                        rx.table.cell(job.id.to(str)),
                        rx.table.cell(job.name),
                        rx.table.cell(job.status),
                        rx.table.cell(job.progress.to(str) + "%"),
                    ),
                ),
            ),
            width="100%",
        ),
        padding="2em",
        width="100%",
    )

app = rx.App(api_transformer=api_transformer)
app.add_page(index, on_load=State.polling_worker)
