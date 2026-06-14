import os
import socket
import sqlite3
import subprocess
import time
from typing import Optional

import pytest
import requests
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/kanban_drag_drop_persistence"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

VALID_COLUMNS = {"TODO", "DOING", "DONE"}

EXPECTED_SEED = {
    ("TODO", 0, "Write spec"),
    ("TODO", 1, "Draft API"),
    ("TODO", 2, "Review PR"),
    ("DOING", 0, "Build UI"),
    ("DOING", 1, "Wire DB"),
    ("DOING", 2, "Add tests"),
    ("DONE", 0, "Setup repo"),
    ("DONE", 1, "Pick stack"),
    ("DONE", 2, "Kickoff"),
}

ALL_TITLES = sorted({title for (_col, _pos, title) in EXPECTED_SEED})


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _kill_servers() -> None:
    """Best-effort cleanup of any lingering reflex / uv / next / uvicorn processes."""
    for pattern in ("reflex run", "uvicorn", "next-server", "next dev", "uv run"):
        subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
    subprocess.run(
        ["fuser", "-k", "3000/tcp", "8000/tcp"],
        capture_output=True,
        text=True,
        check=False,
    )


def _fetch_all_cards() -> list[tuple[int, str, int, str]]:
    """Return all rows as (id, column, position, title) ordered by column, position."""
    assert os.path.isfile(DB_PATH), f"SQLite DB not found at {DB_PATH}"
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, column, position, title FROM card ORDER BY column, position"
        ).fetchall()
        return [(r["id"], r["column"], r["position"], r["title"]) for r in rows]
    finally:
        conn.close()


def _find_card_id(column: str, position: int, title: str) -> int:
    cards = _fetch_all_cards()
    for cid, col, pos, ttl in cards:
        if col == column and pos == position and ttl == title:
            return cid
    raise AssertionError(
        f"Card not found in DB: expected (column={column!r}, position={position!r}, "
        f"title={title!r}). Current rows: {cards!r}"
    )


def _find_card_id_by_title(title: str) -> int:
    cards = _fetch_all_cards()
    for cid, _col, _pos, ttl in cards:
        if ttl == title:
            return cid
    raise AssertionError(
        f"Card with title={title!r} not found. Current rows: {cards!r}"
    )


def _assert_columns_are_dense(label: str) -> None:
    """Assert that each of the three columns has positions 0..n-1 with no gaps/duplicates."""
    cards = _fetch_all_cards()
    by_col: dict[str, list[int]] = {c: [] for c in VALID_COLUMNS}
    for _cid, col, pos, _ttl in cards:
        assert col in VALID_COLUMNS, (
            f"[{label}] Card column {col!r} is not one of {VALID_COLUMNS}; "
            f"all rows: {cards!r}"
        )
        by_col[col].append(pos)
    for col, positions in by_col.items():
        positions_sorted = sorted(positions)
        expected = list(range(len(positions_sorted)))
        assert positions_sorted == expected, (
            f"[{label}] Column {col!r} positions are not 0-dense. "
            f"Got {positions_sorted!r}, expected {expected!r}. All rows: {cards!r}"
        )


def _column_titles_in_order(column: str) -> list[str]:
    cards = _fetch_all_cards()
    return [ttl for (_cid, col, _pos, ttl) in sorted(
        [(cid, col, pos, ttl) for (cid, col, pos, ttl) in cards if col == column],
        key=lambda r: r[2],
    )]


@pytest.fixture(scope="session")
def reflex_server(xprocess):
    """Start the Reflex app once for the session and tear it down at the end."""
    _kill_servers()
    time.sleep(2)

    class Starter(ProcessStarter):
        name = "reflex_kanban_app"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open("localhost", 8000):
                return False
            try:
                ping = requests.get(f"{BACKEND_URL}/ping", timeout=2)
                if ping.status_code != 200:
                    return False
            except requests.RequestException:
                return False
            if not _port_open("localhost", 3000):
                return False
            try:
                root = requests.get(f"{FRONTEND_URL}/", timeout=5)
                if root.status_code != 200:
                    return False
            except requests.RequestException:
                return False
            return True

    xprocess.ensure(Starter.name, Starter)

    yield

    info = xprocess.getinfo(Starter.name)
    try:
        info.terminate()
    except Exception:
        pass
    _kill_servers()


def test_backend_ping_route_alive(reflex_server):
    """Reflex backend reserved `/ping` route must answer 'pong'."""
    response = requests.get(f"{BACKEND_URL}/ping", timeout=5)
    assert response.status_code == 200, (
        f"Expected 200 from {BACKEND_URL}/ping, got {response.status_code}"
    )
    assert "pong" in response.text.lower(), (
        f"Expected 'pong' in /ping response body, got {response.text!r}"
    )


def test_sqlite_db_file_exists(reflex_server):
    """The Reflex SQLite DB file must exist at the documented path after first boot."""
    assert os.path.isfile(DB_PATH), (
        f"Expected SQLite DB at {DB_PATH} after app startup. The app must persist "
        "cards via rx.Model on a sqlite:///reflex.db engine."
    )


def test_seed_data_present(reflex_server):
    """The DB must contain the exact 9 seeded cards described in the task."""
    rows = _fetch_all_cards()
    triples = {(col, pos, ttl) for (_cid, col, pos, ttl) in rows}
    assert triples == EXPECTED_SEED, (
        f"DB seed contents do not match expectations.\nGot:      {sorted(triples)!r}\n"
        f"Expected: {sorted(EXPECTED_SEED)!r}"
    )
    _assert_columns_are_dense("seed")


def test_frontend_root_renders_columns_and_titles(reflex_server):
    """The root page must contain all column labels and all seeded card titles."""
    response = requests.get(f"{FRONTEND_URL}/", timeout=15)
    assert response.status_code == 200, (
        f"Expected 200 from {FRONTEND_URL}/, got {response.status_code}"
    )
    html = response.text
    for column in ("TODO", "DOING", "DONE"):
        assert column in html, (
            f"Expected column label {column!r} in the rendered root page HTML."
        )
    for title in ALL_TITLES:
        assert title in html, (
            f"Expected card title {title!r} to appear in the rendered root page HTML."
        )


def test_move_todo_head_to_done_tail(reflex_server):
    """Moving TODO[0] 'Write spec' to DONE[2] yields the exact post-state."""
    card_id = _find_card_id("TODO", 0, "Write spec")
    response = requests.post(
        f"{BACKEND_URL}/api/cards/move",
        json={"card_id": card_id, "target_column": "DONE", "target_position": 2},
        timeout=10,
    )
    assert response.status_code == 200, (
        f"Expected 200 from /api/cards/move, got {response.status_code}: "
        f"body={response.text!r}"
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise AssertionError(
            f"/api/cards/move did not return JSON. Body={response.text!r}"
        ) from exc
    assert body.get("ok") is True, (
        f"/api/cards/move must return {{'ok': true}} on success. Got {body!r}"
    )

    expected = {
        ("DOING", 0, "Build UI"),
        ("DOING", 1, "Wire DB"),
        ("DOING", 2, "Add tests"),
        ("DONE", 0, "Setup repo"),
        ("DONE", 1, "Pick stack"),
        ("DONE", 2, "Write spec"),
        ("DONE", 3, "Kickoff"),
        ("TODO", 0, "Draft API"),
        ("TODO", 1, "Review PR"),
    }
    rows = _fetch_all_cards()
    triples = {(col, pos, ttl) for (_cid, col, pos, ttl) in rows}
    assert triples == expected, (
        f"After moving TODO[0]→DONE[2] the DB state is wrong.\n"
        f"Got:      {sorted(triples)!r}\nExpected: {sorted(expected)!r}"
    )
    _assert_columns_are_dense("after move_todo_head_to_done_tail")


def test_move_doing_to_todo_head(reflex_server):
    """Moving the current DOING[1] 'Wire DB' to TODO[0] inserts at head and renumbers."""
    card_id = _find_card_id("DOING", 1, "Wire DB")
    response = requests.post(
        f"{BACKEND_URL}/api/cards/move",
        json={"card_id": card_id, "target_column": "TODO", "target_position": 0},
        timeout=10,
    )
    assert response.status_code == 200, (
        f"Expected 200 from /api/cards/move, got {response.status_code}: "
        f"body={response.text!r}"
    )

    todo_titles = _column_titles_in_order("TODO")
    assert todo_titles == ["Wire DB", "Draft API", "Review PR"], (
        f"TODO column order is wrong after move. Got {todo_titles!r}"
    )
    doing_titles = _column_titles_in_order("DOING")
    assert doing_titles == ["Build UI", "Add tests"], (
        f"DOING column order is wrong after move. Got {doing_titles!r}"
    )
    done_titles = _column_titles_in_order("DONE")
    assert done_titles == ["Setup repo", "Pick stack", "Write spec", "Kickoff"], (
        f"DONE column order is wrong after move. Got {done_titles!r}"
    )
    _assert_columns_are_dense("after move_doing_to_todo_head")


def test_same_column_reorder_collapses_gaps(reflex_server):
    """Moving DONE[0] 'Setup repo' to the end of DONE renumbers the column densely."""
    card_id = _find_card_id("DONE", 0, "Setup repo")
    response = requests.post(
        f"{BACKEND_URL}/api/cards/move",
        json={"card_id": card_id, "target_column": "DONE", "target_position": 3},
        timeout=10,
    )
    assert response.status_code == 200, (
        f"Expected 200 from /api/cards/move, got {response.status_code}: "
        f"body={response.text!r}"
    )

    done_titles = _column_titles_in_order("DONE")
    assert done_titles == ["Pick stack", "Write spec", "Kickoff", "Setup repo"], (
        f"DONE column order is wrong after same-column reorder. Got {done_titles!r}"
    )
    _assert_columns_are_dense("after same_column_reorder")


def test_position_clamping_when_target_exceeds_column_size(reflex_server):
    """Moving 'Add tests' to TODO with target_position=999 must land at the tail."""
    card_id = _find_card_id_by_title("Add tests")
    response = requests.post(
        f"{BACKEND_URL}/api/cards/move",
        json={"card_id": card_id, "target_column": "TODO", "target_position": 999},
        timeout=10,
    )
    assert response.status_code == 200, (
        f"Expected 200 from /api/cards/move with clamped position, "
        f"got {response.status_code}: body={response.text!r}"
    )

    todo_titles = _column_titles_in_order("TODO")
    assert todo_titles[-1] == "Add tests", (
        f"After clamping move, 'Add tests' should be last in TODO. "
        f"Got TODO order: {todo_titles!r}"
    )
    _assert_columns_are_dense("after position_clamping")


def test_invalid_card_id_returns_404(reflex_server):
    """POST /api/cards/move with an unknown card_id returns HTTP 404."""
    response = requests.post(
        f"{BACKEND_URL}/api/cards/move",
        json={"card_id": 999999, "target_column": "TODO", "target_position": 0},
        timeout=10,
    )
    assert response.status_code == 404, (
        f"Expected 404 for unknown card_id, got {response.status_code}: "
        f"body={response.text!r}"
    )


def test_invalid_target_column_returns_400(reflex_server):
    """POST /api/cards/move with an invalid target_column returns HTTP 400."""
    cards = _fetch_all_cards()
    assert cards, "DB is empty; cannot pick a card_id for the bad-column test."
    card_id = cards[0][0]
    response = requests.post(
        f"{BACKEND_URL}/api/cards/move",
        json={"card_id": card_id, "target_column": "BACKLOG", "target_position": 0},
        timeout=10,
    )
    assert response.status_code == 400, (
        f"Expected 400 for invalid target_column, got {response.status_code}: "
        f"body={response.text!r}"
    )


def test_page_still_renders_all_titles_after_moves(reflex_server):
    """After several moves, all nine card titles must still be present on the root page."""
    response = requests.get(f"{FRONTEND_URL}/", timeout=15)
    assert response.status_code == 200, (
        f"Expected 200 from {FRONTEND_URL}/, got {response.status_code}"
    )
    html = response.text
    for title in ALL_TITLES:
        assert title in html, (
            f"Expected card title {title!r} to still appear in the rendered root page "
            "HTML after move operations (page must reflect current DB state)."
        )
