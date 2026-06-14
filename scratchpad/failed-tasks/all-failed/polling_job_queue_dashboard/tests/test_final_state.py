import os
import re
import socket
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/myproject"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")
REFLEX_LOG_PATH = "/tmp/reflex.log"

FRONTEND_PORT = 3000
BACKEND_PORT = 8000

API_BASE = f"http://localhost:{BACKEND_PORT}"
FRONTEND_BASE = f"http://localhost:{FRONTEND_PORT}"

EXPECTED_PROGRESS_STEPS = [20, 40, 60, 80, 100]
SINGLE_JOB_TIMEOUT_SEC = 30
BULK_TIMEOUT_SEC = 60


# ---------- helpers ----------

def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_port(port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(port):
            return True
        time.sleep(1.0)
    return False


def _wait_for_http(url: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _run_uv(args, timeout=180, check=True):
    """Run a command inside the project's uv-managed environment."""
    cmd = ["uv", "run", *args]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check:
        assert result.returncode == 0, (
            f"Command {cmd!r} failed with exit code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _sqlite_select_all_jobs():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, status, progress FROM job ORDER BY id ASC")
        return [
            {"id": row[0], "name": row[1], "status": row[2], "progress": row[3]}
            for row in cur.fetchall()
        ]


def _sqlite_count_by_status():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) FROM job GROUP BY status")
        return {row[0]: row[1] for row in cur.fetchall()}


def _sqlite_get_job(job_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, status, progress FROM job WHERE id = ?",
            (job_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"id": row[0], "name": row[1], "status": row[2], "progress": row[3]}


# ---------- fixtures ----------

@pytest.fixture(scope="session", autouse=True)
def _no_stale_ports():
    assert not _port_open(FRONTEND_PORT), (
        f"Port {FRONTEND_PORT} is already in use before the verifier started the "
        f"Reflex server. The task description requires the candidate to terminate "
        f"any background `reflex run` processes after they finish."
    )
    assert not _port_open(BACKEND_PORT), (
        f"Port {BACKEND_PORT} is already in use before the verifier started the "
        f"Reflex server."
    )


@pytest.fixture(scope="session")
def fresh_db():
    # Start from a fresh database file so the job table is empty.
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    _run_uv(["reflex", "db", "migrate"], timeout=240)
    assert os.path.isfile(DB_PATH), (
        f"Expected SQLite DB at {DB_PATH} after running `reflex db migrate`."
    )
    # Verify the job table exists and is empty.
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM job")
        (count,) = cur.fetchone()
    assert count == 0, (
        f"Expected the `job` table to be empty after a fresh migration, "
        f"found {count} rows."
    )
    yield


@pytest.fixture(scope="session")
def reflex_server(fresh_db, xprocess):
    # Truncate any stale log so the ImmutableStateError check is meaningful.
    if os.path.exists(REFLEX_LOG_PATH):
        os.remove(REFLEX_LOG_PATH)
    log_fp = open(REFLEX_LOG_PATH, "w")

    class Starter(ProcessStarter):
        name = "reflex_server"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
            "stdout": log_fp,
            "stderr": subprocess.STDOUT,
        }
        timeout = 360
        terminate_on_interrupt = True

        def startup_check(self):
            return _port_open(FRONTEND_PORT) and _port_open(BACKEND_PORT)

    xprocess.ensure(Starter.name, Starter)

    assert _wait_for_port(FRONTEND_PORT, 120), (
        "Frontend port 3000 did not become ready in time."
    )
    assert _wait_for_port(BACKEND_PORT, 120), (
        "Backend port 8000 did not become ready in time."
    )
    # The candidate may start the polling worker via on_load; hit the index page
    # once so any on_load handler has a chance to fire.
    assert _wait_for_http(f"{FRONTEND_BASE}/", 120), (
        f"Frontend at {FRONTEND_BASE}/ never returned a non-5xx response."
    )

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    log_fp.close()


# ---------- tests ----------

def test_job_table_exists_and_empty(fresh_db):
    # The job table must be created by `reflex db migrate` and start empty.
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, status, progress, created_at FROM job")
        rows = cur.fetchall()
    assert rows == [], (
        f"Expected the `job` table to start empty, found rows: {rows!r}"
    )


def test_empty_counts_endpoint(reflex_server):
    r = requests.get(f"{API_BASE}/api/jobs/counts", timeout=15)
    assert r.status_code == 200, (
        f"GET /api/jobs/counts returned HTTP {r.status_code}: {r.text!r}"
    )
    data = r.json()
    for key in ("PENDING", "RUNNING", "COMPLETED"):
        assert key in data, (
            f"GET /api/jobs/counts response missing key {key!r}; got {data!r}"
        )
        assert data[key] == 0, (
            f"Expected initial count for {key} to be 0, got {data[key]} "
            f"in response {data!r}"
        )


def test_empty_jobs_endpoint(reflex_server):
    r = requests.get(f"{API_BASE}/api/jobs", timeout=15)
    assert r.status_code == 200, (
        f"GET /api/jobs returned HTTP {r.status_code}: {r.text!r}"
    )
    data = r.json()
    assert data == [], (
        f"Expected GET /api/jobs to return [] initially, got {data!r}"
    )


def test_rejects_empty_name(reflex_server):
    r = requests.post(f"{API_BASE}/api/jobs", json={"name": ""}, timeout=15)
    assert 400 <= r.status_code < 500, (
        f"POST /api/jobs with empty name must return HTTP 4xx, got "
        f"{r.status_code}: {r.text!r}"
    )


def test_single_job_lifecycle(reflex_server):
    # 1. Submit one job via the API.
    r = requests.post(f"{API_BASE}/api/jobs", json={"name": "alpha-job"}, timeout=15)
    assert r.status_code in (200, 201), (
        f"POST /api/jobs returned HTTP {r.status_code}: {r.text!r}"
    )
    body = r.json()
    assert "id" in body and isinstance(body["id"], int), (
        f"POST /api/jobs response missing integer 'id': {body!r}"
    )
    assert body.get("name") == "alpha-job", (
        f"POST /api/jobs response 'name' mismatch: {body!r}"
    )
    assert body.get("status") == "PENDING", (
        f"POST /api/jobs response 'status' must be PENDING, got: {body!r}"
    )
    assert body.get("progress") == 0, (
        f"POST /api/jobs response 'progress' must be 0, got: {body!r}"
    )
    alpha_id = body["id"]

    # 2. Poll SQLite directly and record every distinct (status, progress) tuple.
    observed = []
    deadline = time.time() + SINGLE_JOB_TIMEOUT_SEC
    last_tuple = None
    last_progress = -1
    saw_running = False
    while time.time() < deadline:
        row = _sqlite_get_job(alpha_id)
        if row is not None:
            tup = (row["status"], row["progress"])
            if tup != last_tuple:
                observed.append(tup)
                last_tuple = tup
            assert row["progress"] >= last_progress, (
                f"progress regressed from {last_progress} to {row['progress']} "
                f"for job id={alpha_id}. Observation log: {observed!r}"
            )
            last_progress = row["progress"]
            if row["status"] == "RUNNING":
                saw_running = True
            if row["status"] == "COMPLETED" and row["progress"] == 100:
                break
        time.sleep(0.1)

    final = _sqlite_get_job(alpha_id)
    assert final is not None, f"Job id={alpha_id} disappeared from DB."
    assert final["status"] == "COMPLETED" and final["progress"] == 100, (
        f"Job id={alpha_id} did not reach (COMPLETED, 100) within "
        f"{SINGLE_JOB_TIMEOUT_SEC}s. Final row: {final!r}. "
        f"Observation log: {observed!r}"
    )
    assert saw_running, (
        f"Job id={alpha_id} never went through status='RUNNING' before "
        f"COMPLETED. Observation log: {observed!r}"
    )

    # 3. Check that the expected progress milestones occur in the required order.
    progress_history = [progress for (_status, progress) in observed]
    last_index = -1
    for milestone in EXPECTED_PROGRESS_STEPS:
        try:
            idx = next(
                i for i, p in enumerate(progress_history)
                if p == milestone and i > last_index
            )
        except StopIteration:
            raise AssertionError(
                f"Expected progress milestone {milestone} (in the order "
                f"{EXPECTED_PROGRESS_STEPS}) not observed for job id={alpha_id}. "
                f"Observation log: {observed!r}"
            )
        last_index = idx

    # 4. Status/progress correlation invariants.
    for status, progress in observed:
        if progress == 100:
            assert status == "COMPLETED", (
                f"Job id={alpha_id} had progress=100 with status={status!r}. "
                f"Observation log: {observed!r}"
            )
        elif progress == 0:
            assert status in ("PENDING", "RUNNING"), (
                f"Job id={alpha_id} had progress=0 with status={status!r}. "
                f"Observation log: {observed!r}"
            )
        else:
            assert status == "RUNNING", (
                f"Job id={alpha_id} had progress={progress} (0 < p < 100) "
                f"with status={status!r}. Observation log: {observed!r}"
            )


def test_counts_after_single_completion(reflex_server):
    api_resp = requests.get(f"{API_BASE}/api/jobs/counts", timeout=15)
    assert api_resp.status_code == 200, (
        f"GET /api/jobs/counts returned HTTP {api_resp.status_code}: {api_resp.text!r}"
    )
    api_counts = api_resp.json()

    db_counts = _sqlite_count_by_status()
    for status in ("PENDING", "RUNNING", "COMPLETED"):
        assert api_counts.get(status, 0) == db_counts.get(status, 0), (
            f"Count mismatch for status={status!r}: API said "
            f"{api_counts.get(status)}, DB said {db_counts.get(status)}. "
            f"Full API counts: {api_counts!r}, DB counts: {db_counts!r}"
        )
    assert api_counts.get("COMPLETED", 0) == 1, (
        f"Expected exactly 1 COMPLETED job after the single-job lifecycle test, "
        f"got {api_counts!r}"
    )


def test_get_jobs_reflects_completion(reflex_server):
    r = requests.get(f"{API_BASE}/api/jobs", timeout=15)
    assert r.status_code == 200, (
        f"GET /api/jobs returned HTTP {r.status_code}: {r.text!r}"
    )
    data = r.json()
    assert isinstance(data, list) and len(data) == 1, (
        f"Expected exactly 1 job in GET /api/jobs after single-job lifecycle, "
        f"got: {data!r}"
    )
    job = data[0]
    assert job.get("name") == "alpha-job", (
        f"Expected the single job name to be 'alpha-job', got: {job!r}"
    )
    assert job.get("status") == "COMPLETED", (
        f"Expected the single job status to be 'COMPLETED', got: {job!r}"
    )
    assert job.get("progress") == 100, (
        f"Expected the single job progress to be 100, got: {job!r}"
    )


def test_bulk_submission_consistency(reflex_server):
    # Submit three more jobs in close succession.
    for name in ("beta-1", "beta-2", "beta-3"):
        r = requests.post(f"{API_BASE}/api/jobs", json={"name": name}, timeout=15)
        assert r.status_code in (200, 201), (
            f"POST /api/jobs for name={name!r} returned HTTP {r.status_code}: "
            f"{r.text!r}"
        )

    # While the batch is processing, sample counts repeatedly to verify
    # invariants (RUNNING <= 1, and counts sum equals total DB rows).
    deadline = time.time() + BULK_TIMEOUT_SEC
    completed_count = 0
    while time.time() < deadline:
        r = requests.get(f"{API_BASE}/api/jobs/counts", timeout=15)
        assert r.status_code == 200, (
            f"GET /api/jobs/counts returned HTTP {r.status_code}: {r.text!r}"
        )
        counts = r.json()
        running = counts.get("RUNNING", 0)
        pending = counts.get("PENDING", 0)
        completed = counts.get("COMPLETED", 0)
        assert running <= 1, (
            f"Expected at most 1 RUNNING job at any moment (worker is "
            f"single-threaded), saw RUNNING={running} in {counts!r}"
        )
        db_total = sum(_sqlite_count_by_status().values())
        assert (pending + running + completed) == db_total, (
            f"Counts API ({counts!r}) sum does not equal DB total row count "
            f"({db_total}). Counts must mirror the database exactly."
        )
        if completed >= 4:
            completed_count = completed
            break
        time.sleep(0.5)
    else:
        raise AssertionError(
            f"Bulk batch did not complete within {BULK_TIMEOUT_SEC}s. "
            f"Final counts: {counts!r}"
        )

    assert completed_count == 4, (
        f"Expected 4 COMPLETED jobs after the bulk batch, got {completed_count}. "
        f"Counts: {counts!r}"
    )
    assert counts.get("PENDING", -1) == 0 and counts.get("RUNNING", -1) == 0, (
        f"After all jobs completed, both PENDING and RUNNING must be 0; "
        f"got: {counts!r}"
    )

    # GET /api/jobs ordering and names.
    r = requests.get(f"{API_BASE}/api/jobs", timeout=15)
    assert r.status_code == 200, (
        f"GET /api/jobs returned HTTP {r.status_code}: {r.text!r}"
    )
    jobs = r.json()
    assert isinstance(jobs, list) and len(jobs) == 4, (
        f"Expected 4 jobs in GET /api/jobs after bulk batch, got: {jobs!r}"
    )
    ids = [j["id"] for j in jobs]
    assert ids == sorted(ids), (
        f"GET /api/jobs must be sorted by id ascending, got ids: {ids!r}"
    )
    names = [j["name"] for j in jobs]
    assert names == ["alpha-job", "beta-1", "beta-2", "beta-3"], (
        f"GET /api/jobs name ordering must reflect insertion order, got: "
        f"{names!r}"
    )
    for j in jobs:
        assert j["status"] == "COMPLETED", (
            f"Every job must be COMPLETED after the batch settles, got: {j!r}"
        )
        assert j["progress"] == 100, (
            f"Every COMPLETED job must have progress=100, got: {j!r}"
        )


def test_frontend_reachable(reflex_server):
    last_exc = None
    for _ in range(30):
        try:
            r = requests.get(f"{FRONTEND_BASE}/", timeout=10)
            if r.status_code == 200 and r.text:
                lowered = r.text.lower()
                assert "<html" in lowered or "<!doctype" in lowered, (
                    f"Frontend at port {FRONTEND_PORT} did not return HTML."
                )
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(2)
    raise AssertionError(
        f"Frontend at {FRONTEND_BASE}/ never returned HTTP 200 with HTML. "
        f"Last exception: {last_exc!r}"
    )


def test_no_immutable_state_error_in_logs(reflex_server):
    assert os.path.exists(REFLEX_LOG_PATH), (
        f"Expected Reflex log at {REFLEX_LOG_PATH}."
    )
    log_text = Path(REFLEX_LOG_PATH).read_text(errors="replace")
    assert "ImmutableStateError" not in log_text, (
        "Reflex backend logged an ImmutableStateError; the background polling "
        "worker must wrap state mutations in `async with self:`."
    )
    assert "Background task StateProxy is immutable" not in log_text, (
        "Reflex backend logged the StateProxy-immutable error; the background "
        "polling worker must wrap state mutations in `async with self:`."
    )


def test_source_uses_required_reflex_primitives(reflex_server):
    py_sources = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [
            d for d in dirs
            if d not in (".venv", "__pycache__", ".web", ".git", "node_modules",
                         "alembic")
        ]
        for fn in files:
            if fn.endswith(".py"):
                py_sources.append(os.path.join(root, fn))
    assert py_sources, f"No Python source files found under {PROJECT_DIR}."

    combined = ""
    for path in py_sources:
        try:
            combined += "\n" + Path(path).read_text(errors="replace")
        except OSError:
            continue

    assert re.search(r"@rx\.event\(\s*background\s*=\s*True\s*\)", combined), (
        "Could not find a `@rx.event(background=True)` decorator anywhere "
        f"under {PROJECT_DIR}. The polling worker must be a background event "
        "handler."
    )
    assert re.search(r"async\s+with\s+self\b", combined), (
        "Could not find an `async with self:` block. Background state mutations "
        "must acquire the State lock."
    )
    assert re.search(r"@rx\.var\(\s*cache\s*=\s*True\s*\)", combined), (
        "Could not find a `@rx.var(cache=True)` decorator. The status-count "
        "computed var must be cached."
    )
    assert re.search(r"rx\.foreach\b", combined), (
        "Could not find `rx.foreach` usage. The job table must be rendered "
        "with `rx.foreach`."
    )
    assert re.search(r"api_transformer\b", combined), (
        "Could not find `api_transformer` usage. The custom FastAPI routes "
        "must be mounted via the `api_transformer` argument of `rx.App`."
    )
