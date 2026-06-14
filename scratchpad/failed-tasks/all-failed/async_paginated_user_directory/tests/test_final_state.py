import json
import math
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

PAGE_SIZE = 10

EXPECTED_USERNAMES = [
    "alice", "bob", "carol", "dave", "Foobar",
    "erin", "frank", "grace", "heidi", "ivan",
    "judy", "kate", "BarFoo", "leo", "mallory",
    "niaj", "olivia", "peggy", "quinn", "rupert",
    "fooDude", "sybil", "trent", "uma", "victor",
    "wendy", "xavier", "yasmin", "zach", "FOOFighter",
    "amy", "ben", "chad", "don", "eli",
    "fern", "gus", "hank", "ivy", "jack",
    "king", "deepFoo", "luna", "milo", "nora",
    "otto", "pete",
]
TOTAL_USERS = len(EXPECTED_USERNAMES)  # 47
FOO_IDS = [i + 1 for i, n in enumerate(EXPECTED_USERNAMES) if "foo" in n.lower()]
TOTAL_PAGES = math.ceil(TOTAL_USERS / PAGE_SIZE)  # 5


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


def _run_uv(args, timeout=120, check=True):
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


def _find_seed_command():
    """Pick the candidate's seed entry point. Prefer ./seed.py, fall back to a few common names."""
    for candidate in ("seed.py", "seed_users.py", "scripts/seed.py"):
        full = os.path.join(PROJECT_DIR, candidate)
        if os.path.isfile(full):
            return ["python", candidate]
    return None


def _parse_probe_json(stdout: str) -> dict:
    """The probe must print a JSON object. Tolerate extra leading/trailing lines."""
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    assert lines, f"probe.py produced empty stdout:\n{stdout!r}"
    # Walk from the bottom and accept the first line that parses as a JSON object.
    for ln in reversed(lines):
        try:
            data = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise AssertionError(
        f"probe.py stdout did not contain a JSON object on any line:\n{stdout!r}"
    )


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
def prepared_db():
    # Make sure the schema is up to date.
    _run_uv(["reflex", "db", "migrate"], timeout=180)

    seed_cmd = _find_seed_command()
    assert seed_cmd is not None, (
        f"Could not find a seed script (looked for seed.py, seed_users.py, "
        f"scripts/seed.py under {PROJECT_DIR}). The task requires a deterministic "
        f"seeding mechanism."
    )
    # Run seed twice to confirm idempotency.
    _run_uv(seed_cmd, timeout=120)
    _run_uv(seed_cmd, timeout=120)

    assert os.path.isfile(DB_PATH), f"Expected SQLite DB at {DB_PATH} after seeding."
    yield


@pytest.fixture(scope="session")
def reflex_server(prepared_db, xprocess):
    # Make sure no leftover log confuses the ImmutableStateError check.
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
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            # Reflex serves the frontend on 3000 and the backend on 8000.
            return _port_open(FRONTEND_PORT) and _port_open(BACKEND_PORT)

    xprocess.ensure(Starter.name, Starter)
    # Give Reflex a small grace period to finish hydrating the index route.
    assert _wait_for_port(FRONTEND_PORT, 60), "Frontend port did not become ready."
    assert _wait_for_port(BACKEND_PORT, 60), "Backend port did not become ready."

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    log_fp.close()


# ---------- tests ----------

def test_database_seeded_with_47_users(prepared_db):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user")
        (count,) = cur.fetchone()
        assert count == TOTAL_USERS, (
            f"Expected exactly {TOTAL_USERS} users in `user` table, found {count}."
        )


def test_database_seed_rows_exact(prepared_db):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, email FROM user ORDER BY id ASC")
        rows = cur.fetchall()
    assert len(rows) == TOTAL_USERS, (
        f"Expected {TOTAL_USERS} rows, found {len(rows)}."
    )
    for idx, (uid, username, email) in enumerate(rows, start=1):
        expected_username = EXPECTED_USERNAMES[idx - 1]
        expected_email = f"{expected_username.lower()}@example.com"
        assert uid == idx, (
            f"Row {idx}: expected id={idx}, got id={uid}. Seed must insert in order."
        )
        assert username == expected_username, (
            f"Row {idx}: expected username {expected_username!r}, got {username!r}."
        )
        assert email == expected_email, (
            f"Row {idx}: expected email {expected_email!r}, got {email!r}."
        )


def test_database_case_insensitive_foo_count(prepared_db):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user WHERE LOWER(username) LIKE '%foo%'")
        (count,) = cur.fetchone()
    assert count == len(FOO_IDS), (
        f"Expected {len(FOO_IDS)} usernames matching case-insensitive 'foo', "
        f"found {count}."
    )


def test_frontend_reachable(reflex_server):
    last_exc = None
    for _ in range(30):
        try:
            r = requests.get(f"http://localhost:{FRONTEND_PORT}/", timeout=10)
            if r.status_code == 200 and r.text:
                assert "<html" in r.text.lower() or "<!doctype" in r.text.lower(), (
                    f"Frontend at port {FRONTEND_PORT} did not return HTML."
                )
                return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        time.sleep(2)
    raise AssertionError(
        f"Frontend at http://localhost:{FRONTEND_PORT}/ never returned HTTP 200. "
        f"Last exception: {last_exc!r}"
    )


def test_probe_page_1_no_search(reflex_server):
    result = _run_uv(["python", "probe.py", "--page", "1"], timeout=120)
    data = _parse_probe_json(result.stdout)
    assert data["page"] == 1
    assert data["page_size"] == PAGE_SIZE
    assert data["total_users"] == TOTAL_USERS
    assert data["total_pages"] == TOTAL_PAGES
    ids = [item["id"] for item in data["items"]]
    assert ids == list(range(1, 11)), f"Page 1 ids: expected 1..10, got {ids}."
    # Spot check the "Foobar" row at index 4 (id=5).
    row_5 = next(item for item in data["items"] if item["id"] == 5)
    assert row_5["username"] == "Foobar", (
        f"Expected user id=5 username 'Foobar', got {row_5['username']!r}."
    )
    assert row_5["email"] == "foobar@example.com", (
        f"Expected user id=5 email 'foobar@example.com', got {row_5['email']!r}."
    )


def test_probe_page_2_returns_items_11_to_20(reflex_server):
    result = _run_uv(["python", "probe.py", "--page", "2"], timeout=120)
    data = _parse_probe_json(result.stdout)
    assert data["page"] == 2
    assert data["total_users"] == TOTAL_USERS
    assert data["total_pages"] == TOTAL_PAGES
    ids = [item["id"] for item in data["items"]]
    assert ids == list(range(11, 21)), f"Page 2 ids: expected 11..20, got {ids}."
    row_13 = next(item for item in data["items"] if item["id"] == 13)
    assert row_13["username"] == "BarFoo", (
        f"Expected user id=13 username 'BarFoo', got {row_13['username']!r}."
    )


def test_probe_final_partial_page(reflex_server):
    result = _run_uv(["python", "probe.py", "--page", "5"], timeout=120)
    data = _parse_probe_json(result.stdout)
    assert data["page"] == 5
    assert data["total_pages"] == TOTAL_PAGES
    assert data["total_users"] == TOTAL_USERS
    ids = [item["id"] for item in data["items"]]
    assert ids == list(range(41, 48)), f"Page 5 ids: expected 41..47, got {ids}."
    assert len(data["items"]) == 7, (
        f"Final page must contain 7 items, got {len(data['items'])}."
    )


def test_probe_out_of_range_page(reflex_server):
    result = _run_uv(["python", "probe.py", "--page", "6"], timeout=120)
    data = _parse_probe_json(result.stdout)
    assert data["page"] == 6
    assert data["total_users"] == TOTAL_USERS
    assert data["total_pages"] == TOTAL_PAGES
    assert data["items"] == [], (
        f"Out-of-range page must return [] items, got {data['items']!r}."
    )


def test_probe_search_lowercase_foo(reflex_server):
    result = _run_uv(
        ["python", "probe.py", "--page", "1", "--search", "foo"], timeout=120
    )
    data = _parse_probe_json(result.stdout)
    assert data["total_users"] == len(FOO_IDS), (
        f"Search 'foo' total_users: expected {len(FOO_IDS)}, got {data['total_users']}."
    )
    assert data["total_pages"] == 1, (
        f"Search 'foo' total_pages: expected 1, got {data['total_pages']}."
    )
    ids = [item["id"] for item in data["items"]]
    assert ids == FOO_IDS, (
        f"Search 'foo' returned ids {ids}, expected {FOO_IDS}."
    )


def test_probe_search_uppercase_foo_same_result(reflex_server):
    result = _run_uv(
        ["python", "probe.py", "--page", "1", "--search", "FOO"], timeout=120
    )
    data = _parse_probe_json(result.stdout)
    assert data["total_users"] == len(FOO_IDS), (
        f"Search 'FOO' total_users: expected {len(FOO_IDS)}, got {data['total_users']}."
    )
    ids = [item["id"] for item in data["items"]]
    assert ids == FOO_IDS, (
        f"Search 'FOO' must be case-insensitive: got ids {ids}, expected {FOO_IDS}."
    )


def test_probe_search_with_no_match(reflex_server):
    result = _run_uv(
        ["python", "probe.py", "--page", "1", "--search", "zzz_no_match"], timeout=120
    )
    data = _parse_probe_json(result.stdout)
    assert data["total_users"] == 0, (
        f"Search with no match total_users: expected 0, got {data['total_users']}."
    )
    assert data["total_pages"] == 0, (
        f"Search with no match total_pages: expected 0, got {data['total_pages']}."
    )
    assert data["items"] == [], (
        f"Search with no match must return [] items, got {data['items']!r}."
    )


def test_no_immutable_state_error_in_logs(reflex_server):
    assert os.path.exists(REFLEX_LOG_PATH), (
        f"Expected Reflex log at {REFLEX_LOG_PATH}."
    )
    log_text = Path(REFLEX_LOG_PATH).read_text(errors="replace")
    assert "ImmutableStateError" not in log_text, (
        "Reflex backend logged an ImmutableStateError; the background handler "
        "must wrap state mutations in `async with self:`."
    )
    assert "Background task StateProxy is immutable" not in log_text, (
        "Reflex backend logged the StateProxy-immutable error; the background "
        "handler must wrap state mutations in `async with self:`."
    )


def test_source_uses_background_event_and_state_lock(reflex_server):
    py_sources = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        # Skip caches and the uv-managed venv.
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
        "Could not find a `@rx.event(background=True)` decorator anywhere under "
        f"{PROJECT_DIR}. The directory fetch must be a background event handler."
    )
    assert re.search(r"async\s+with\s+self\b", combined), (
        "Could not find an `async with self:` block. Background state mutations "
        "must acquire the State lock."
    )
    assert re.search(r"rx\.asession\s*\(", combined), (
        "Could not find a `rx.asession(` usage. The background handler must use "
        "the async DB session."
    )
    assert re.search(r"page_size[^\n=]*=\s*10\b", combined), (
        "Could not find `page_size = 10` in the State definition. Page size must "
        "be fixed at 10."
    )
