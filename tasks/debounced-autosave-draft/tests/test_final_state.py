import os
import socket
import sqlite3
import subprocess

import pytest
import requests
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/note_app"
DB_PATH = "/home/user/note_app/reflex.db"

FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback (::1),
# so a server listening on 127.0.0.1 would never be reached and the readiness
# check would hang for the full timeout.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"

# The exact draft text the browser agent must type into the editor. The SQLite
# check below scans the database for this marker string.
DRAFT_TEXT = "autosave-check-9f3a2b: the quick brown fox"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        return s.connect_ex((HOST, port)) == 0


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Prepare a clean database, apply migrations, then start `reflex run`."""
    # Start from a clean database so the restore check is deterministic.
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Apply the migrations the executor created so the draft table exists on a
    # fresh database. This uses the project's uv-managed environment.
    migrate = subprocess.run(
        ["uv", "run", "reflex", "db", "migrate"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    print("=== reflex db migrate stdout ===")
    print(migrate.stdout)
    print("=== reflex db migrate stderr ===")
    print(migrate.stderr)

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        # CRITICAL: set `env` as a class attribute, NEVER inside popen_kwargs,
        # otherwise Popen raises "got multiple values for keyword argument 'env'".
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the frontend, which can take a while.
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open(FRONTEND_PORT) or not _port_open(BACKEND_PORT):
                return False
            try:
                resp = requests.get(BASE_URL, timeout=30)
                return resp.status_code < 500
            except requests.RequestException:
                return False

    info = xprocess.getinfo(Starter.name)
    printed = 0

    def capture_logs(tag):
        nonlocal printed
        try:
            with open(info.logpath, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []
        new = lines[printed:]
        printed = len(lines)
        print(f"===== [{tag}] {Starter.name} log begin =====")
        print("".join(new))
        print(f"===== [{tag}] {Starter.name} log end =====")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_debounced_autosave_flow(start_app, browser_verifier):
    """End-to-end: initial Unsaved state, debounced autosave, and restore on reload."""
    reason = (
        "The app at / is a note editor with a text area and a save-status "
        "indicator. Typing is debounced; a short quiet period after the last "
        "keystroke, a background task autosaves the draft to SQLite and the "
        "status changes from 'Unsaved' to 'Saved' with a timestamp. On page "
        "load the most recently saved draft is restored into the text area."
    )
    truth = (
        f"Navigate to {BASE_URL} and wait for the editor to fully load so the "
        f"text area is editable. Verify the status indicator shows 'Unsaved' "
        f"and the text area is initially empty. Click the text area and type "
        f"exactly: {DRAFT_TEXT} . Do not click any save button (there is none). "
        f"Wait about 8 seconds for the automatic debounced autosave to finish, "
        f"then verify the status indicator now shows a 'Saved' label that "
        f"includes a timestamp. Next, reload the page and wait for it to load "
        f"again; verify the text area is automatically restored to contain the "
        f"text '{DRAFT_TEXT}' and the status again shows 'Saved'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_debounced_autosave_flow",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_draft_persisted_in_sqlite(start_app):
    """The autosaved draft text must be stored in the local SQLite database."""
    assert os.path.exists(DB_PATH), (
        f"Expected the SQLite database file at {DB_PATH} to exist after autosave."
    )

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        tables = [
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        found = False
        for table in tables:
            try:
                rows = cur.execute(f'SELECT * FROM "{table}"').fetchall()
            except sqlite3.DatabaseError:
                continue
            for row in rows:
                for value in row:
                    if isinstance(value, str) and DRAFT_TEXT in value:
                        found = True
                        break
                if found:
                    break
            if found:
                break
    finally:
        con.close()

    assert found, (
        f"Expected a stored draft containing '{DRAFT_TEXT}' in the SQLite "
        f"database at {DB_PATH}, but no such row was found. Tables: {tables}"
    )
