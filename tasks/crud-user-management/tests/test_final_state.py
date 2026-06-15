import os
import re
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_DIR = "/home/user/myproject"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")
WEB_DIR = os.path.join(PROJECT_DIR, ".web")

EXCLUDE_DIRS = {".venv", ".web", "alembic", "__pycache__", ".git", "node_modules"}


def _iter_py_sources(root: str):
    root_path = Path(root)
    if not root_path.is_dir():
        return
    for path in root_path.rglob("*.py"):
        parts = set(path.relative_to(root_path).parts)
        if parts & EXCLUDE_DIRS:
            continue
        yield path


def _read_all_python_sources(root: str) -> str:
    chunks = []
    for path in _iter_py_sources(root):
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n\n# === FILE BOUNDARY ===\n\n".join(chunks)


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def _kill_reflex_processes():
    for pattern in ("reflex run", "next-server", "next start", "reflex.app"):
        subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture(scope="session")
def project_sources() -> str:
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."
    return _read_all_python_sources(PROJECT_DIR)


@pytest.fixture(scope="session")
def reflex_dev_server():
    """Start `uv run reflex run` in the background and tear it down at the end."""
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."

    _kill_reflex_processes()
    time.sleep(2.0)

    log_path = "/tmp/reflex_run.log"
    log_file = open(log_path, "wb")
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    deadline = time.time() + 300.0  # first run compiles the frontend; allow plenty of time
    ready = False
    last_error: Exception | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            log_file.flush()
            tail = ""
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
                    tail = fh.read()[-4000:]
            except OSError:
                pass
            pytest.fail(
                f"'uv run reflex run' exited early with code {proc.returncode}.\n"
                f"Recent log:\n{tail}"
            )
        if _port_open("localhost", 3000):
            try:
                with urllib.request.urlopen("http://localhost:3000/", timeout=10) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = exc
        time.sleep(2.0)

    if not ready:
        log_file.flush()
        tail = ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
                tail = fh.read()[-4000:]
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
        _kill_reflex_processes()
        log_file.close()
        pytest.fail(
            "Reflex dev server did not become ready on http://localhost:3000 within timeout. "
            f"Last error: {last_error}.\nRecent log:\n{tail}"
        )

    try:
        yield proc
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=15)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        _kill_reflex_processes()
        try:
            log_file.close()
        except Exception:
            pass


def test_database_file_exists():
    assert os.path.isfile(DB_PATH), (
        f"Expected SQLite database file at {DB_PATH}. Did the executor run "
        "'uv run reflex db init && uv run reflex db makemigrations --message init && "
        "uv run reflex db migrate'?"
    )


def test_user_table_schema():
    assert os.path.isfile(DB_PATH), f"Database file {DB_PATH} does not exist."
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user';"
        )
        row = cur.fetchone()
        assert row is not None, (
            "No 'user' table found in reflex.db. The User model must be declared with table=True "
            "and the alembic migrations must be applied."
        )

        cur.execute("PRAGMA table_info(user);")
        cols = cur.fetchall()
    finally:
        conn.close()

    by_name = {c[1]: c for c in cols}

    assert "id" in by_name, f"'user' table is missing an 'id' column. Got columns: {list(by_name)}."
    id_col = by_name["id"]
    assert "INT" in id_col[2].upper(), (
        f"'id' column should be an integer type, got '{id_col[2]}'."
    )
    assert id_col[5] == 1, (
        f"'id' column should be the primary key (pk=1), got pk={id_col[5]}."
    )

    assert "username" in by_name, (
        f"'user' table is missing a 'username' column. Got columns: {list(by_name)}."
    )
    username_type = by_name["username"][2].upper()
    assert any(t in username_type for t in ("TEXT", "VARCHAR", "CHAR", "STRING")), (
        f"'username' column should be a text type, got '{by_name['username'][2]}'."
    )

    assert "email" in by_name, (
        f"'user' table is missing an 'email' column. Got columns: {list(by_name)}."
    )
    email_type = by_name["email"][2].upper()
    assert any(t in email_type for t in ("TEXT", "VARCHAR", "CHAR", "STRING")), (
        f"'email' column should be a text type, got '{by_name['email'][2]}'."
    )

    assert "is_active" in by_name, (
        f"'user' table is missing an 'is_active' column. Got columns: {list(by_name)}."
    )
    is_active_type = by_name["is_active"][2].upper()
    assert any(
        t in is_active_type for t in ("BOOL", "INT", "TINYINT", "NUMERIC")
    ), f"'is_active' column should be a boolean/integer type, got '{by_name['is_active'][2]}'."


def test_user_model_definition(project_sources: str):
    # Look for `class User(rx.Model, table=True)` (allow whitespace variations).
    class_pattern = re.compile(
        r"class\s+User\s*\(\s*rx\.Model\s*,\s*table\s*=\s*True\s*\)\s*:",
        re.MULTILINE,
    )
    assert class_pattern.search(project_sources), (
        "Could not find `class User(rx.Model, table=True):` in the project sources."
    )

    assert re.search(r"username\s*:\s*str", project_sources), (
        "User model is missing `username: str` field."
    )
    assert re.search(r"email\s*:\s*str", project_sources), (
        "User model is missing `email: str` field."
    )
    assert re.search(r"is_active\s*:\s*bool\s*=\s*True", project_sources), (
        "User model is missing `is_active: bool = True` field."
    )


def test_state_exposes_users_var_and_load_event(project_sources: str):
    assert re.search(
        r"users\s*:\s*list\s*\[\s*User\s*\]",
        project_sources,
    ), "State class must declare `users: list[User]` base var."

    assert re.search(r"def\s+load_users\s*\(\s*self", project_sources), (
        "State class must define a `load_users` event handler."
    )


def test_event_handlers_present(project_sources: str):
    assert re.search(r"def\s+create_user\s*\(\s*self", project_sources), (
        "State must define a `create_user` event handler."
    )
    assert re.search(
        r"def\s+delete_user\s*\(\s*self\s*,\s*user_id",
        project_sources,
    ), "State must define a `delete_user(self, user_id)` event handler."
    assert re.search(
        r"def\s+toggle_active\s*\(\s*self\s*,\s*user_id",
        project_sources,
    ), "State must define a `toggle_active(self, user_id)` event handler."


def test_sync_rx_session_used_at_least_twice(project_sources: str):
    matches = re.findall(r"with\s+rx\.session\s*\(\s*\)", project_sources)
    assert len(matches) >= 2, (
        f"Expected at least 2 `with rx.session()` usages (create + delete/toggle), "
        f"found {len(matches)}."
    )

    assert "session.delete(" in project_sources and "session.commit()" in project_sources, (
        "Expected `session.delete(...)` and `session.commit()` for the delete handler."
    )
    assert "session.add(" in project_sources, (
        "Expected `session.add(...)` for the create handler."
    )


def test_exported_frontend_contains_required_labels():
    # Trigger an export to ensure the .web tree is materialized regardless of dev-server state.
    result = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, (
        f"`uv run reflex export --frontend-only --no-zip` failed (exit={result.returncode}).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    assert os.path.isdir(WEB_DIR), (
        f"Expected the Reflex web build output at {WEB_DIR} after `reflex export`."
    )

    needles = {"Create": False, "Delete": False, "Toggle": False}
    text_extensions = {".html", ".js", ".jsx", ".ts", ".tsx", ".json", ".css", ".mjs"}

    for path in Path(WEB_DIR).rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in text_extensions:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label in list(needles):
            if not needles[label] and label in text:
                needles[label] = True
        if all(needles.values()):
            break

    missing = [k for k, v in needles.items() if not v]
    assert not missing, (
        f"Exported frontend under {WEB_DIR} is missing literal labels: {missing}."
    )


def test_dev_server_serves_root(reflex_dev_server):
    with urllib.request.urlopen("http://localhost:3000/", timeout=15) as resp:
        assert resp.status == 200, (
            f"GET http://localhost:3000/ returned status {resp.status}; expected 200."
        )
        body = resp.read().decode("utf-8", errors="ignore")

    assert len(body) > 0, "GET http://localhost:3000/ returned an empty body."
