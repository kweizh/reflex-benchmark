import os
import socket
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
from xprocess import ProcessStarter

from pochi_verifier import PochiVerifier


PROJECT_DIR = "/home/user/myproject"
DB_PATH = "/home/user/myproject/reflex.db"
LOG_PATH = "/tmp/reflex_run.log"
FIXTURE_PATH = "/tmp/people_fixture.csv"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000

FIXTURE_CONTENT = (
    "name,email,age\n"
    "alice,alice@example.com,30\n"
    "bob,bob@example.com,25\n"
    "carol,carol@example.com,45\n"
    "dave,dave@example.com,22\n"
    "eve,eve@example.com,33\n"
    "missing_email,,40\n"
    "bad_age,frank@example.com,not_a_number\n"
    "negative_age,grace@example.com,-1\n"
)

EXPECTED_VALID_ROWS = [
    ("alice", "alice@example.com", 30),
    ("bob", "bob@example.com", 25),
    ("carol", "carol@example.com", 45),
    ("dave", "dave@example.com", 22),
    ("eve", "eve@example.com", 33),
]

SUMMARY_SUBSTRING = "Processed 8 rows: 5 valid, 3 invalid"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(1.0)
    return False


@pytest.fixture(scope="session", autouse=True)
def prepare_fixture_and_db():
    # Kill any stale dev server first.
    for pat in ("reflex run", "next-server", "uvicorn"):
        subprocess.run(["pkill", "-f", pat], check=False, capture_output=True)
    for port in (FRONTEND_PORT, BACKEND_PORT):
        subprocess.run(["fuser", "-k", f"{port}/tcp"], check=False, capture_output=True)
    time.sleep(2)

    # Recreate the verification fixture.
    Path(FIXTURE_PATH).write_text(FIXTURE_CONTENT, encoding="utf-8")

    # Wipe the DB so we count only this run's inserts.
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Apply migrations from a clean DB (best-effort init then strict migrate).
    subprocess.run(
        ["uv", "run", "reflex", "db", "init"],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=300,
    )
    subprocess.run(
        ["uv", "run", "reflex", "db", "makemigrations", "--message", "verify"],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=300,
    )
    migrate = subprocess.run(
        ["uv", "run", "reflex", "db", "migrate"],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=300,
    )
    assert migrate.returncode == 0, (
        f"`reflex db migrate` failed before starting the server: "
        f"stdout={migrate.stdout!r} stderr={migrate.stderr!r}"
    )

    # Reset the log file.
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
    Path(LOG_PATH).touch()

    yield

    # Teardown for safety even if xprocess fixture missed something.
    for pat in ("reflex run", "next-server", "uvicorn"):
        subprocess.run(["pkill", "-f", pat], check=False, capture_output=True)
    for port in (FRONTEND_PORT, BACKEND_PORT):
        subprocess.run(["fuser", "-k", f"{port}/tcp"], check=False, capture_output=True)


@pytest.fixture(scope="session")
def reflex_server(xprocess, prepare_fixture_and_db):
    log_fh = open(LOG_PATH, "a", buffering=1)

    class Starter(ProcessStarter):
        name = "reflex_server"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
            "stdout": log_fh,
            "stderr": subprocess.STDOUT,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            return _port_open("localhost", FRONTEND_PORT) and _port_open("localhost", BACKEND_PORT)

    xprocess.ensure(Starter.name, Starter)

    # Allow the websocket / hydration to settle before traffic.
    time.sleep(5)
    assert _wait_for_port("localhost", FRONTEND_PORT, 60.0), (
        f"Frontend port {FRONTEND_PORT} not reachable after starting `uv run reflex run`."
    )
    assert _wait_for_port("localhost", BACKEND_PORT, 60.0), (
        f"Backend port {BACKEND_PORT} not reachable after starting `uv run reflex run`."
    )

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    try:
        log_fh.close()
    except Exception:
        pass


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


def test_database_file_exists_after_migrations(reflex_server):
    assert os.path.isfile(DB_PATH), (
        f"SQLite database {DB_PATH} was not created by `reflex db migrate`."
    )


def test_browser_upload_and_summary(reflex_server, browser_verifier):
    reason = (
        "The Reflex app must accept a CSV upload and report progress and a "
        "final summary on the page using a background event handler."
    )
    truth = (
        f"Navigate to http://localhost:{FRONTEND_PORT}/. "
        f"Locate the file input that belongs to the upload dropzone with id 'csv_upload'. "
        f"Set its value to the local file '{FIXTURE_PATH}'. "
        "Click the button (or upload trigger) on the page that submits the chosen file. "
        "Wait up to 60 seconds for the upload to finish processing. "
        f"Verify that the page renders the exact substring '{SUMMARY_SUBSTRING}' "
        "somewhere on the page after processing completes. "
        "Verify that a progress bar (or progress indicator) on the page reaches a value of 100 "
        "(check `aria-valuenow=\"100\"` or a visible text of '100'). "
        "Verify that at least three error messages are visible on the page and that they collectively "
        "reference the 1-based input row numbers 6, 7 and 8."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_browser_upload_and_summary",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def _find_people_table(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    required_cols = {"name", "email", "age"}
    candidates = []
    for t in tables:
        if t.startswith("sqlite_") or t == "alembic_version":
            continue
        cur.execute(f'PRAGMA table_info("{t}")')
        cols = {row[1] for row in cur.fetchall()}
        if required_cols.issubset(cols):
            candidates.append(t)
    assert candidates, (
        f"No table with columns {sorted(required_cols)} was found in {DB_PATH}. "
        f"Tables present: {tables}"
    )
    assert len(candidates) == 1, (
        f"Expected exactly one table with columns {sorted(required_cols)} in {DB_PATH}, "
        f"found: {candidates}"
    )
    return candidates[0]


def test_sqlite_contains_exactly_valid_rows(reflex_server):
    # Give the background task a brief moment to flush in case the browser
    # check returned the instant the summary appeared.
    time.sleep(2)
    conn = sqlite3.connect(DB_PATH)
    try:
        table = _find_people_table(conn)
        cur = conn.cursor()
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        (count,) = cur.fetchone()
        assert count == len(EXPECTED_VALID_ROWS), (
            f"Expected {len(EXPECTED_VALID_ROWS)} rows in table '{table}', found {count}."
        )

        cur.execute(f'SELECT name, email, age FROM "{table}" ORDER BY name')
        actual = [(r[0], r[1], int(r[2])) for r in cur.fetchall()]
        assert actual == EXPECTED_VALID_ROWS, (
            f"Database contents do not match expected valid rows. "
            f"Expected {EXPECTED_VALID_ROWS}, got {actual}."
        )

        # None of the invalid records may have leaked into the table.
        cur.execute(f'SELECT name FROM "{table}"')
        names = {row[0] for row in cur.fetchall()}
        for forbidden in ("missing_email", "bad_age", "negative_age"):
            assert forbidden not in names, (
                f"Invalid record '{forbidden}' was inserted into the database; "
                f"validation contract violated."
            )
    finally:
        conn.close()


def test_no_immutable_state_error_in_log(reflex_server):
    # Read the entire reflex run log captured by xprocess.
    assert os.path.isfile(LOG_PATH), f"Server log {LOG_PATH} is missing."
    content = Path(LOG_PATH).read_text(encoding="utf-8", errors="replace")
    assert "ImmutableStateError" not in content, (
        "Server log contains ImmutableStateError; the background task is mutating "
        "state outside of an `async with self:` block."
    )
