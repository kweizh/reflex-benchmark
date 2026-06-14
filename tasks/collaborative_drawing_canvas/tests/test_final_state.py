"""Final state verification for collaborative_drawing_canvas.

These tests start the Reflex backend (per the truth field of task.json) and
exercise the REST API contract, the SQLite schema, and the compiled frontend
artifact. The Reflex app itself is **not** imported by the verifier; we only
use `subprocess`, the stdlib `sqlite3` module, and `requests`.
"""

import json
import os
import re
import socket
import sqlite3
import subprocess
import time
from typing import Optional

import pytest
import requests
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/myproject"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")
BACKEND_PORT = 8000
BASE_URL = f"http://localhost:{BACKEND_PORT}"
LOG_PATH = "/tmp/reflex_backend.log"


REQUIRED_STROKE_COLUMNS = {
    "id",
    "x1",
    "y1",
    "x2",
    "y2",
    "color",
    "session_id",
}


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _wait_for_backend(url: str, total: float = 120.0) -> bool:
    deadline = time.time() + total
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200 and "pong" in resp.text.lower():
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _kill_stale_servers() -> None:
    for pat in ("reflex run", "reflex.utils.exec", "next"):
        subprocess.run(["pkill", "-f", pat], check=False)
    # Best-effort port release
    subprocess.run(["fuser", "-k", "8000/tcp"], check=False)
    subprocess.run(["fuser", "-k", "3000/tcp"], check=False)
    time.sleep(1)


@pytest.fixture(scope="session", autouse=True)
def _prepare_environment():
    """Run uv sync + db migrate exactly once before the backend is started."""
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist."
    )

    _kill_stale_servers()

    # Remove any old backend log to make assertions deterministic.
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)

    sync = subprocess.run(
        ["uv", "sync"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert sync.returncode == 0, (
        f"`uv sync` failed in {PROJECT_DIR}: "
        f"stdout={sync.stdout!r} stderr={sync.stderr!r}"
    )

    migrate = subprocess.run(
        ["uv", "run", "reflex", "db", "migrate"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert migrate.returncode == 0, (
        f"`reflex db migrate` failed: "
        f"stdout={migrate.stdout!r} stderr={migrate.stderr!r}"
    )

    yield

    _kill_stale_servers()
    if os.path.exists(LOG_PATH):
        try:
            os.remove(LOG_PATH)
        except OSError:
            pass


@pytest.fixture(scope="session")
def backend(xprocess, _prepare_environment):
    class Starter(ProcessStarter):
        name = "reflex_backend"
        args = [
            "uv",
            "run",
            "reflex",
            "run",
            "--backend-only",
            "--backend-port",
            str(BACKEND_PORT),
            "--loglevel",
            "info",
        ]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
            "stdout": open(LOG_PATH, "w"),
            "stderr": subprocess.STDOUT,
        }
        timeout = 240
        terminate_on_interrupt = True

        def startup_check(self) -> bool:
            if not _port_open("127.0.0.1", BACKEND_PORT):
                return False
            try:
                resp = requests.get(f"{BASE_URL}/ping", timeout=2)
                return resp.status_code == 200 and "pong" in resp.text.lower()
            except Exception:
                return False

    xprocess.ensure(Starter.name, Starter)

    # An extra safety wait for the background polling task to settle.
    assert _wait_for_backend(f"{BASE_URL}/ping", total=60), (
        "Reflex backend did not respond to /ping after fixture startup."
    )

    yield BASE_URL

    info = xprocess.getinfo(Starter.name)
    info.terminate()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_database_file_exists():
    assert os.path.isfile(DB_PATH), (
        f"Expected SQLite database at {DB_PATH} after migrations."
    )


def test_stroke_table_schema():
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("PRAGMA table_info(stroke);")
        rows = cursor.fetchall()
    finally:
        conn.close()

    assert rows, "Table `stroke` does not exist in reflex.db."

    column_names = {row[1] for row in rows}
    missing = REQUIRED_STROKE_COLUMNS - column_names
    assert not missing, (
        f"Stroke table is missing required columns: {sorted(missing)}. "
        f"Found columns: {sorted(column_names)}"
    )

    pk_columns = [row[1] for row in rows if row[5] >= 1]
    assert pk_columns == ["id"], (
        f"Expected `id` to be the sole primary key column, got: {pk_columns}"
    )


def test_ping_endpoint(backend):
    resp = requests.get(f"{backend}/ping", timeout=5)
    assert resp.status_code == 200, (
        f"GET /ping expected 200, got {resp.status_code}: {resp.text!r}"
    )
    assert "pong" in resp.text.lower(), (
        f"GET /ping expected to contain 'pong', got: {resp.text!r}"
    )


def test_strokes_crud_contract(backend):
    # Baseline listing
    resp = requests.get(f"{backend}/api/strokes", timeout=10)
    assert resp.status_code == 200, (
        f"GET /api/strokes expected 200, got {resp.status_code}: {resp.text!r}"
    )
    initial = resp.json()
    assert isinstance(initial, list), (
        f"GET /api/strokes must return a JSON array, got: {type(initial).__name__}"
    )
    baseline = len(initial)

    # Create stroke #1
    payload_one = {
        "x1": 12.5,
        "y1": 17.0,
        "x2": 88.25,
        "y2": 110.75,
        "color": "#00FFAA",
        "session_id": "sess-canvas-01",
    }
    resp = requests.post(
        f"{backend}/api/strokes",
        json=payload_one,
        timeout=10,
    )
    assert resp.status_code == 201, (
        f"POST /api/strokes expected 201, got {resp.status_code}: {resp.text!r}"
    )
    body = resp.json()
    for key, expected in payload_one.items():
        assert body.get(key) == expected, (
            f"POST response missing/mismatched field {key!r}: {body!r}"
        )
    assert isinstance(body.get("id"), int), (
        f"POST response must include integer `id`, got: {body!r}"
    )
    created_id = body["id"]

    # DB row count must have grown by exactly 1
    conn = sqlite3.connect(DB_PATH)
    try:
        (count_after_one,) = conn.execute(
            "SELECT COUNT(*) FROM stroke;"
        ).fetchone()
    finally:
        conn.close()
    assert count_after_one == baseline + 1, (
        f"Expected stroke row count {baseline + 1} after first insert, "
        f"got {count_after_one}."
    )

    # GET should reflect the new row
    resp = requests.get(f"{backend}/api/strokes", timeout=10)
    assert resp.status_code == 200, (
        f"GET /api/strokes (post insert) expected 200, got {resp.status_code}"
    )
    listing = resp.json()
    assert len(listing) == baseline + 1, (
        f"GET /api/strokes expected {baseline + 1} items, got {len(listing)}"
    )
    ids = {item.get("id") for item in listing if isinstance(item, dict)}
    assert created_id in ids, (
        f"Newly inserted stroke id {created_id} not present in listing ids {ids}"
    )

    # Create stroke #2 and exercise polling stability
    payload_two = {
        "x1": 1.0,
        "y1": 2.0,
        "x2": 3.0,
        "y2": 4.0,
        "color": "#FF0000",
        "session_id": "sess-canvas-02",
    }
    resp = requests.post(
        f"{backend}/api/strokes",
        json=payload_two,
        timeout=10,
    )
    assert resp.status_code == 201, (
        f"Second POST /api/strokes expected 201, got {resp.status_code}"
    )

    # Give the background poller multiple cycles to run (>= 6 cycles of 250 ms)
    time.sleep(1.5)

    resp = requests.get(f"{backend}/api/strokes", timeout=10)
    assert resp.status_code == 200, (
        f"GET /api/strokes (final) expected 200, got {resp.status_code}"
    )
    final_listing = resp.json()
    assert len(final_listing) == baseline + 2, (
        f"GET /api/strokes expected {baseline + 2} items after second insert, "
        f"got {len(final_listing)}."
    )


def test_background_poller_no_immutable_state_error():
    assert os.path.isfile(LOG_PATH), (
        f"Expected backend log at {LOG_PATH} after running the server."
    )
    with open(LOG_PATH, "r", errors="replace") as fh:
        log_text = fh.read()
    assert "ImmutableStateError" not in log_text, (
        "Backend log contains `ImmutableStateError` — the background polling task "
        "is mutating state outside of `async with self`."
    )


def test_compiled_frontend_has_svg_foreach():
    web_pages = os.path.join(PROJECT_DIR, ".web", "pages")
    assert os.path.isdir(web_pages), (
        f"Expected compiled frontend directory at {web_pages}. "
        "Did `reflex run` complete compilation?"
    )

    candidate: Optional[str] = None
    for ext in ("index.js", "index.jsx"):
        path = os.path.join(web_pages, ext)
        if os.path.isfile(path):
            candidate = path
            break

    assert candidate is not None, (
        f"Expected `index.js` or `index.jsx` under {web_pages}, found: "
        f"{os.listdir(web_pages)}"
    )

    with open(candidate, "r", errors="replace") as fh:
        content = fh.read()

    assert re.search(r"\bsvg\b", content, re.IGNORECASE), (
        f"Compiled page {candidate} does not reference an `svg` tag."
    )
    assert re.search(r"\bline\b", content, re.IGNORECASE), (
        f"Compiled page {candidate} does not reference a `line` tag — make sure "
        "`rx.foreach` emits `<line>` SVG elements."
    )
