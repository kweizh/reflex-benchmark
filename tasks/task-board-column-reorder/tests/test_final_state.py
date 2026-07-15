import os
import socket
import sqlite3
import subprocess
import time

import pytest
import requests
from xprocess import ProcessStarter

from playwright.sync_api import sync_playwright

PROJECT_DIR = "/home/user/task_board"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")

# Bind/connect over IPv4 explicitly to avoid IPv6 loopback (::1) resolution issues.
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"

REQUIRED_COLUMNS = {"title", "status", "position"}

# Expected board state after each interaction step.
# Each state maps a status to the ordered list of card titles (top -> bottom).
SEED_STATE = {
    "todo": ["Write spec", "Design schema", "Draft tests"],
    "doing": ["Build API", "Wire UI"],
    "done": ["Kickoff meeting"],
}
STATE_AFTER_MOVE_RIGHT_DRAFT = {
    "todo": ["Write spec", "Design schema"],
    "doing": ["Build API", "Wire UI", "Draft tests"],
    "done": ["Kickoff meeting"],
}
STATE_AFTER_MOVE_UP_DRAFT = {
    "todo": ["Write spec", "Design schema"],
    "doing": ["Build API", "Draft tests", "Wire UI"],
    "done": ["Kickoff meeting"],
}
STATE_AFTER_MOVE_RIGHT_BUILD = {
    "todo": ["Write spec", "Design schema"],
    "doing": ["Draft tests", "Wire UI"],
    "done": ["Kickoff meeting", "Build API"],
}
STATE_AFTER_MOVE_DOWN_KICKOFF = {
    "todo": ["Write spec", "Design schema"],
    "doing": ["Draft tests", "Wire UI"],
    "done": ["Build API", "Kickoff meeting"],
}
STATE_AFTER_MOVE_LEFT_BUILD = {
    "todo": ["Write spec", "Design schema"],
    "doing": ["Draft tests", "Wire UI", "Build API"],
    "done": ["Kickoff meeting"],
}


def _find_card_table(conn):
    """Locate the SQLite table that stores cards (has title, status, position)."""
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    for name in tables:
        cols = {row[1] for row in conn.execute(f'PRAGMA table_info("{name}")').fetchall()}
        if REQUIRED_COLUMNS.issubset(cols):
            return name
    return None


def _read_board():
    """Return {'id': ..., 'title': ..., 'status': ..., 'position': ...} rows from the DB."""
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        table = _find_card_table(conn)
        if table is None:
            return None
        rows = conn.execute(
            f'SELECT id, title, status, position FROM "{table}"'
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return [
        {"id": r[0], "title": r[1], "status": r[2], "position": r[3]} for r in rows
    ]


def _ordered_state(rows):
    """Build {status: [titles ordered by position]} from raw rows."""
    state = {}
    for status in ("todo", "doing", "done"):
        col_rows = sorted(
            (r for r in rows if r["status"] == status), key=lambda r: r["position"]
        )
        state[status] = [r["title"] for r in col_rows]
    return state


def _positions_contiguous(rows):
    for status in ("todo", "doing", "done"):
        positions = sorted(r["position"] for r in rows if r["status"] == status)
        if positions != list(range(len(positions))):
            return False, status, positions
    return True, None, None


def _card_id(rows, title):
    for r in rows:
        if r["title"] == title:
            return r["id"]
    return None


def _wait_for_state(expected, timeout=45.0):
    """Poll the DB until the ordered board state matches `expected`."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        rows = _read_board()
        if rows is not None:
            last = _ordered_state(rows)
            if last == expected:
                return rows
        time.sleep(0.5)
    raise AssertionError(
        f"Timed out waiting for board state.\nExpected: {expected}\nActual:   {last}"
    )


def _wait_for_row_count(count, timeout=90.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        rows = _read_board()
        if rows is not None:
            last = len(rows)
            if last == count:
                return rows
        time.sleep(0.5)
    raise AssertionError(
        f"Timed out waiting for {count} card rows in the database; last count was {last}."
    )


def _reset_database():
    """Delete the SQLite DB and recreate the schema from the app's migrations."""
    for suffix in ("", "-wal", "-shm"):
        path = DB_PATH + suffix
        if os.path.exists(path):
            os.remove(path)
    result = subprocess.run(
        ["uv", "run", "reflex", "db", "migrate"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        "`uv run reflex db migrate` failed to create the schema on a fresh database:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


@pytest.fixture(scope="session")
def app_server(xprocess):
    # Ensure a deterministic, freshly-seeded starting point before the server starts.
    _reset_database()

    class Starter(ProcessStarter):
        name = "task_board_app"
        # CI=1 keeps `reflex run` fully non-interactive/headless.
        env = {**os.environ, "CI": "1"}
        args = ["uv", "run", "reflex", "run", "--env", "dev"]
        popen_kwargs = {"cwd": PROJECT_DIR, "text": True}
        timeout = 600
        terminate_on_interrupt = True
        max_read_lines = 5000

        def startup_check(self):
            for port in (BACKEND_PORT, FRONTEND_PORT):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    if s.connect_ex((HOST, port)) != 0:
                        return False
            try:
                resp = requests.get(BASE_URL, timeout=20)
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
        except OSError:
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

    yield BASE_URL

    capture_logs("TEARDOWN")
    info.terminate()


@pytest.fixture(scope="session")
def page(app_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()
        # Loading the page triggers the on-load seeding of the empty database.
        pg.goto(app_server, wait_until="networkidle")
        yield pg
        browser.close()


def _dom_count(page, column):
    locator = page.locator(f'[data-testid="count-{column}"]').first
    locator.wait_for(state="visible", timeout=30000)
    return int(locator.inner_text().strip())


def _wait_dom_counts(page, expected, timeout=30.0):
    """Poll the rendered per-column count elements until they match `expected`."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = {c: _dom_count(page, c) for c in ("todo", "doing", "done")}
        except Exception:
            last = None
        if last == expected:
            return
        time.sleep(0.5)
    raise AssertionError(
        f"Timed out waiting for DOM counts.\nExpected: {expected}\nActual:   {last}"
    )


def _click_move(page, rows, title, direction):
    card_id = _card_id(rows, title)
    assert card_id is not None, f"Could not find card titled {title!r} in the database."
    selector = f'[data-testid="move-{direction}-{card_id}"]'
    button = page.locator(selector).first
    button.wait_for(state="visible", timeout=15000)
    button.click()


def _counts_of(state):
    return {status: len(titles) for status, titles in state.items()}


def test_backend_is_serving(app_server):
    """The Reflex backend must be reachable on its port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        assert s.connect_ex((HOST, BACKEND_PORT)) == 0, (
            f"Reflex backend is not accepting connections on {HOST}:{BACKEND_PORT}."
        )


def test_board_reorder_flow(page):
    # Step 1: initial seed + counts.
    rows = _wait_for_row_count(6)
    assert _ordered_state(rows) == SEED_STATE, (
        f"Initial seeded board does not match the required seed.\n"
        f"Expected: {SEED_STATE}\nActual: {_ordered_state(rows)}"
    )
    ok, status, positions = _positions_contiguous(rows)
    assert ok, f"Seed positions in column {status!r} are not contiguous 0-based: {positions}"
    _wait_dom_counts(page, _counts_of(SEED_STATE))

    # Step 2: move 'Draft tests' right (To Do -> Doing, appended to end).
    _click_move(page, rows, "Draft tests", "right")
    rows = _wait_for_state(STATE_AFTER_MOVE_RIGHT_DRAFT)
    ok, status, positions = _positions_contiguous(rows)
    assert ok, f"After move-right, column {status!r} positions not contiguous: {positions}"
    _wait_dom_counts(page, _counts_of(STATE_AFTER_MOVE_RIGHT_DRAFT))

    # Step 3: move 'Draft tests' up within Doing (swap with the card above).
    _click_move(page, rows, "Draft tests", "up")
    rows = _wait_for_state(STATE_AFTER_MOVE_UP_DRAFT)
    ok, status, positions = _positions_contiguous(rows)
    assert ok, f"After move-up, column {status!r} positions not contiguous: {positions}"
    _wait_dom_counts(page, _counts_of(STATE_AFTER_MOVE_UP_DRAFT))

    # Step 4: move 'Build API' right (Doing -> Done, appended to end).
    _click_move(page, rows, "Build API", "right")
    rows = _wait_for_state(STATE_AFTER_MOVE_RIGHT_BUILD)
    ok, status, positions = _positions_contiguous(rows)
    assert ok, f"After second move-right, column {status!r} positions not contiguous: {positions}"
    _wait_dom_counts(page, _counts_of(STATE_AFTER_MOVE_RIGHT_BUILD))

    # Step 5: move 'Kickoff meeting' down within Done (swap with the card below).
    _click_move(page, rows, "Kickoff meeting", "down")
    rows = _wait_for_state(STATE_AFTER_MOVE_DOWN_KICKOFF)
    ok, status, positions = _positions_contiguous(rows)
    assert ok, f"After move-down, column {status!r} positions not contiguous: {positions}"
    _wait_dom_counts(page, _counts_of(STATE_AFTER_MOVE_DOWN_KICKOFF))

    # Step 6: move 'Build API' left (Done -> Doing, appended to end).
    _click_move(page, rows, "Build API", "left")
    rows = _wait_for_state(STATE_AFTER_MOVE_LEFT_BUILD)
    ok, status, positions = _positions_contiguous(rows)
    assert ok, f"After move-left, column {status!r} positions not contiguous: {positions}"
    _wait_dom_counts(page, _counts_of(STATE_AFTER_MOVE_LEFT_BUILD))

    # Step 7: persistence across reload (no re-seeding, state unchanged).
    page.reload(wait_until="networkidle")
    rows = _wait_for_state(STATE_AFTER_MOVE_LEFT_BUILD)
    assert len(rows) == 6, f"Reload changed the number of cards; expected 6, got {len(rows)}."
    _wait_dom_counts(page, _counts_of(STATE_AFTER_MOVE_LEFT_BUILD))

    # Step 8: no-op edges. Moving a To Do card further left and a top-of-column
    # card up must not change any state.
    _click_move(page, rows, "Write spec", "left")
    _click_move(page, rows, "Draft tests", "up")
    time.sleep(2)
    rows_after = _read_board()
    assert rows_after is not None, "Database unreadable after no-op edge moves."
    assert _ordered_state(rows_after) == STATE_AFTER_MOVE_LEFT_BUILD, (
        "No-op edge moves changed the board.\n"
        f"Expected: {STATE_AFTER_MOVE_LEFT_BUILD}\nActual: {_ordered_state(rows_after)}"
    )
    ok, status, positions = _positions_contiguous(rows_after)
    assert ok, f"After no-op edges, column {status!r} positions not contiguous: {positions}"
    _wait_dom_counts(page, _counts_of(STATE_AFTER_MOVE_LEFT_BUILD))
