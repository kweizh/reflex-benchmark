import json
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


def _parse_probe_json(stdout: str) -> dict:
    """Parse the last JSON object printed on stdout."""
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    assert lines, f"probe.py produced empty stdout:\n{stdout!r}"
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


def _probe(*args, timeout=120, check=True) -> dict:
    result = _run_uv(["python", "probe.py", *args], timeout=timeout, check=check)
    return _parse_probe_json(result.stdout)


def _list_sqlite_tables(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cur.fetchall()]


def _list_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _list_fks(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA foreign_key_list({table})")
    # Each row: (id, seq, table, from, to, on_update, on_delete, match)
    return [(row[2], row[3], row[4]) for row in cur.fetchall()]


def _find_link_table(conn) -> str:
    tables = _list_sqlite_tables(conn)
    candidates = []
    for t in tables:
        if t in ("note", "tag", "alembic_version"):
            continue
        fks = _list_fks(conn, t)
        refs_note = any(ref_table == "note" and ref_col == "id" for ref_table, _, ref_col in fks)
        refs_tag = any(ref_table == "tag" and ref_col == "id" for ref_table, _, ref_col in fks)
        if refs_note and refs_tag:
            candidates.append(t)
    assert candidates, (
        f"No link/junction table found in the SQLite schema. Tables: {tables}. "
        "The many-to-many relationship must be implemented via a separate link "
        "table that has foreign keys into note(id) and tag(id)."
    )
    # Prefer the first one if multiple
    return candidates[0]


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
    _run_uv(["reflex", "db", "migrate"], timeout=240)
    assert os.path.isfile(DB_PATH), (
        f"Expected SQLite DB at {DB_PATH} after `reflex db migrate`."
    )

    # Wipe rows so each verifier run starts from a clean state. We do NOT drop
    # tables because the schema is part of what we're verifying.
    with sqlite3.connect(DB_PATH) as conn:
        link_table = _find_link_table(conn)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {link_table}")
        cur.execute("DELETE FROM note")
        cur.execute("DELETE FROM tag")
        # Reset autoincrement counters if sqlite_sequence is present.
        try:
            cur.execute("DELETE FROM sqlite_sequence")
        except sqlite3.OperationalError:
            pass
        conn.commit()
    yield


@pytest.fixture(scope="session")
def reflex_server(prepared_db, xprocess):
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
            return _port_open(FRONTEND_PORT) and _port_open(BACKEND_PORT)

    xprocess.ensure(Starter.name, Starter)
    assert _wait_for_port(FRONTEND_PORT, 60), "Frontend port did not become ready."
    assert _wait_for_port(BACKEND_PORT, 60), "Backend port did not become ready."

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    log_fp.close()


# ---------- schema tests ----------

def test_schema_has_note_and_tag_tables(prepared_db):
    with sqlite3.connect(DB_PATH) as conn:
        tables = _list_sqlite_tables(conn)
        assert "note" in tables, (
            f"Expected a `note` table in the schema; got tables: {tables}."
        )
        assert "tag" in tables, (
            f"Expected a `tag` table in the schema; got tables: {tables}."
        )
        note_cols = _list_columns(conn, "note")
        assert "id" in note_cols and "content" in note_cols, (
            f"`note` table must contain at least `id` and `content` columns; got {note_cols}."
        )
        tag_cols = _list_columns(conn, "tag")
        assert "id" in tag_cols and "name" in tag_cols, (
            f"`tag` table must contain at least `id` and `name` columns; got {tag_cols}."
        )


def test_schema_has_link_table_for_many_to_many(prepared_db):
    with sqlite3.connect(DB_PATH) as conn:
        link_table = _find_link_table(conn)
        fks = _list_fks(conn, link_table)
        ref_targets = {(ref_table, ref_col) for ref_table, _, ref_col in fks}
        assert ("note", "id") in ref_targets, (
            f"Link table `{link_table}` is missing a foreign key into note(id). "
            f"Foreign keys: {fks}."
        )
        assert ("tag", "id") in ref_targets, (
            f"Link table `{link_table}` is missing a foreign key into tag(id). "
            f"Foreign keys: {fks}."
        )


# ---------- CLI / behavioral tests ----------

def test_counts_starts_clean(prepared_db):
    data = _probe("counts")
    assert data == {"notes": 0, "tags": 0, "links": 0}, (
        f"After cleaning, `probe.py counts` must return all zeros, got {data!r}."
    )


def test_ensure_tag_is_idempotent(prepared_db):
    data = _probe("ensure-tag", "--name", "alpha")
    assert data.get("created") is True, (
        f"First `ensure-tag --name alpha` must report created=true; got {data!r}."
    )
    assert data.get("name") == "alpha"
    alpha_id = data["id"]

    data2 = _probe("ensure-tag", "--name", "alpha")
    assert data2.get("created") is False, (
        f"Second `ensure-tag --name alpha` must report created=false; got {data2!r}."
    )
    assert data2.get("id") == alpha_id, (
        f"Idempotent `ensure-tag` must return the same id; got {data2!r} vs first id {alpha_id}."
    )

    data3 = _probe("ensure-tag", "--name", "beta")
    assert data3.get("created") is True
    assert data3.get("name") == "beta"

    counts = _probe("counts")
    assert counts == {"notes": 0, "tags": 2, "links": 0}, (
        f"After two ensure-tags, counts must be notes=0/tags=2/links=0; got {counts!r}."
    )


def test_create_note_with_two_existing_tags_adds_three_rows(prepared_db):
    before = _probe("counts")
    assert before == {"notes": 0, "tags": 2, "links": 0}, (
        f"Precondition failed: baseline counts must be notes=0/tags=2/links=0; got {before!r}."
    )

    created = _probe(
        "create", "--content", "first note", "--tags", "alpha,beta"
    )
    assert isinstance(created.get("id"), int) and created["id"] > 0, (
        f"create must return a positive integer `id`; got {created!r}."
    )
    assert created.get("content") == "first note", (
        f"create must echo content; got {created!r}."
    )
    assert sorted(created.get("tags") or []) == ["alpha", "beta"], (
        f"create must echo sorted tags ['alpha','beta']; got {created!r}."
    )

    after = _probe("counts")
    assert after == {"notes": 1, "tags": 2, "links": 2}, (
        f"Creating a note with 2 pre-existing tags must add exactly 1 note row, "
        f"0 tag rows, and 2 link rows. Before={before!r}, after={after!r}. "
        f"That is exactly 3 new rows total across the 3 tables."
    )


def test_create_note_with_new_tag_creates_tag_row(prepared_db):
    created = _probe(
        "create", "--content", "second note", "--tags", "beta,gamma"
    )
    assert sorted(created.get("tags") or []) == ["beta", "gamma"], (
        f"create must echo sorted tags ['beta','gamma']; got {created!r}."
    )

    counts = _probe("counts")
    assert counts == {"notes": 2, "tags": 3, "links": 4}, (
        f"Creating a 2nd note with one new tag must produce notes=2/tags=3/links=4; "
        f"got {counts!r}."
    )


def test_list_without_filter_returns_all(prepared_db):
    data = _probe("list")
    notes = data.get("notes")
    assert isinstance(notes, list) and len(notes) == 2, (
        f"`list` without filter must return 2 notes; got {data!r}."
    )
    ids = [n["id"] for n in notes]
    assert ids == sorted(ids), f"`list` must return notes in ascending id order; got {ids}."
    contents = [n["content"] for n in notes]
    assert "first note" in contents and "second note" in contents, (
        f"`list` must include both notes; got {data!r}."
    )

    by_content = {n["content"]: n for n in notes}
    assert sorted(by_content["first note"]["tags"]) == ["alpha", "beta"], (
        f"Note 'first note' must keep tags ['alpha','beta']; got {by_content['first note']!r}."
    )
    assert sorted(by_content["second note"]["tags"]) == ["beta", "gamma"], (
        f"Note 'second note' must keep tags ['beta','gamma']; got {by_content['second note']!r}."
    )


def test_filter_by_tag_or_semantics(prepared_db):
    # alpha → only the first note
    data = _probe("list", "--filter", "alpha")
    notes = data.get("notes") or []
    contents = [n["content"] for n in notes]
    assert contents == ["first note"], (
        f"Filter 'alpha' must return only ['first note']; got {contents!r}."
    )

    # gamma → only the second note
    data = _probe("list", "--filter", "gamma")
    contents = [n["content"] for n in data.get("notes") or []]
    assert contents == ["second note"], (
        f"Filter 'gamma' must return only ['second note']; got {contents!r}."
    )

    # beta → both notes
    data = _probe("list", "--filter", "beta")
    contents = sorted(n["content"] for n in data.get("notes") or [])
    assert contents == ["first note", "second note"], (
        f"Filter 'beta' must return both notes; got {contents!r}."
    )

    # alpha,gamma → OR semantics, returns both
    data = _probe("list", "--filter", "alpha,gamma")
    contents = sorted(n["content"] for n in data.get("notes") or [])
    assert contents == ["first note", "second note"], (
        f"Filter 'alpha,gamma' (OR semantics) must return both notes; got {contents!r}."
    )

    # nonexistent → empty list
    data = _probe("list", "--filter", "nonexistent_tag")
    assert data.get("notes") == [], (
        f"Filter on a nonexistent tag must return an empty list; got {data!r}."
    )


def test_all_tags_is_union_of_attached(prepared_db):
    data = _probe("all-tags")
    assert data.get("all_tags") == ["alpha", "beta", "gamma"], (
        f"`all-tags` must return the union of attached tags, sorted ascending; "
        f"got {data!r}."
    )


def test_set_tags_replaces_and_does_not_delete_tag_rows(prepared_db):
    listing = _probe("list", "--filter", "alpha")
    first_id = listing["notes"][0]["id"]

    data = _probe("set-tags", "--id", str(first_id), "--tags", "beta")
    assert sorted(data.get("tags") or []) == ["beta"], (
        f"After set-tags, the note must only have ['beta']; got {data!r}."
    )

    counts = _probe("counts")
    assert counts == {"notes": 2, "tags": 3, "links": 3}, (
        f"After set-tags, expected notes=2/tags=3/links=3 (alpha tag row preserved, "
        f"alpha link row removed); got {counts!r}."
    )

    # alpha is orphaned now and must drop out of all-tags.
    all_tags = _probe("all-tags").get("all_tags")
    assert all_tags == ["beta", "gamma"], (
        f"After set-tags, `all-tags` must equal ['beta','gamma'] (alpha is orphaned); "
        f"got {all_tags!r}."
    )

    # Tag row for alpha must still exist in the DB.
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tag WHERE name='alpha'")
        (n,) = cur.fetchone()
    assert n == 1, (
        "Tag row 'alpha' must NOT be deleted when a note stops referencing it."
    )


def test_update_changes_content_only(prepared_db):
    listing = _probe("list", "--filter", "beta")
    # Pick the note that previously had tags ['beta'] only (the first one).
    note = next(
        n for n in listing["notes"]
        if n["content"] == "first note" and sorted(n["tags"]) == ["beta"]
    )
    target_id = note["id"]

    data = _probe(
        "update", "--id", str(target_id), "--content", "first note edited"
    )
    assert data.get("content") == "first note edited", (
        f"`update` must echo the new content; got {data!r}."
    )

    # Verify content changed and tags unchanged.
    listing = _probe("list", "--filter", "beta")
    target = next(n for n in listing["notes"] if n["id"] == target_id)
    assert target["content"] == "first note edited", (
        f"After update, content for note id={target_id} must be 'first note edited'; got {target!r}."
    )
    assert sorted(target["tags"]) == ["beta"], (
        f"After update, tags for note id={target_id} must remain ['beta']; got {target!r}."
    )


def test_delete_removes_links_but_not_tags(prepared_db):
    listing = _probe("list")
    second = next(n for n in listing["notes"] if n["content"] == "second note")
    second_id = second["id"]

    res = _probe("delete", "--id", str(second_id))
    assert res == {"id": second_id, "deleted": True}, (
        f"`delete --id {second_id}` must return id and deleted=true; got {res!r}."
    )

    counts = _probe("counts")
    assert counts == {"notes": 1, "tags": 3, "links": 1}, (
        f"After deleting the second note, expected notes=1/tags=3/links=1; got {counts!r}. "
        f"Tag rows must NOT be deleted by note deletion."
    )

    # Direct sqlite check: no link row references the deleted note id; and all 3
    # tag names still exist in the tag table.
    with sqlite3.connect(DB_PATH) as conn:
        link_table = _find_link_table(conn)
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {link_table} WHERE note_id = ?", (second_id,))
        (link_count_for_deleted,) = cur.fetchone()
        assert link_count_for_deleted == 0, (
            f"No row in link table `{link_table}` may reference note_id={second_id} "
            f"after delete; found {link_count_for_deleted}."
        )
        cur.execute("SELECT name FROM tag ORDER BY name ASC")
        tag_names = [row[0] for row in cur.fetchall()]
    assert tag_names == ["alpha", "beta", "gamma"], (
        f"After delete, all three tag rows must remain; got {tag_names!r}."
    )

    # all_tags now reflects only the tags still attached to a note (beta).
    all_tags = _probe("all-tags").get("all_tags")
    assert all_tags == ["beta"], (
        f"After deleting the second note, `all-tags` must equal ['beta']; got {all_tags!r}."
    )


# ---------- server-level checks ----------

def test_frontend_reachable(reflex_server):
    last_exc = None
    for _ in range(30):
        try:
            r = requests.get(f"http://localhost:{FRONTEND_PORT}/", timeout=10)
            if r.status_code == 200 and r.text:
                body = r.text.lower()
                assert "<html" in body or "<!doctype" in body, (
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


def test_no_immutable_state_error_in_logs(reflex_server):
    assert os.path.exists(REFLEX_LOG_PATH), (
        f"Expected Reflex log at {REFLEX_LOG_PATH}."
    )
    log_text = Path(REFLEX_LOG_PATH).read_text(errors="replace")
    assert "ImmutableStateError" not in log_text, (
        "Reflex backend logged an ImmutableStateError."
    )
    assert "Background task StateProxy is immutable" not in log_text, (
        "Reflex backend logged the StateProxy-immutable error."
    )


# ---------- source-code contract checks ----------

def _collect_py_sources() -> str:
    py_sources = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [
            d for d in dirs
            if d not in (".venv", "__pycache__", ".web", ".git",
                         "node_modules", "alembic")
        ]
        for fn in files:
            if fn.endswith(".py"):
                py_sources.append(os.path.join(root, fn))
    combined = ""
    for path in py_sources:
        try:
            combined += "\n" + Path(path).read_text(errors="replace")
        except OSError:
            continue
    return combined


def test_source_uses_link_model_and_state_contracts(reflex_server):
    combined = _collect_py_sources()
    assert combined, f"No Python source files found under {PROJECT_DIR}."

    assert re.search(r"Relationship\s*\([^)]*link_model\s*=", combined, re.DOTALL), (
        "Could not find an `sqlmodel.Relationship(..., link_model=...)` call. "
        "The many-to-many between Note and Tag must use a link table via "
        "`link_model=`."
    )
    assert re.search(r"\bselected_tags\b\s*:", combined), (
        "Could not find a `selected_tags:` field on any State class."
    )
    assert re.search(
        r"@rx\.(?:cached_var\b|var\s*\(\s*[^)]*cache\s*=\s*True[^)]*\))",
        combined,
    ), (
        "Could not find a cached computed var (e.g. `@rx.var(cache=True)` or "
        "`@rx.cached_var`) for `all_tags`."
    )
    assert re.search(r"\ball_tags\b", combined), (
        "Could not find a reference to `all_tags` anywhere in the source."
    )
    assert re.search(r"rx\.foreach\s*\(", combined), (
        "Could not find a `rx.foreach(` usage. The displayed notes list must use "
        "`rx.foreach`."
    )
    assert re.search(r"rx\.cond\s*\(", combined), (
        "Could not find a `rx.cond(` usage. The `selected_tags` filter must use "
        "`rx.cond`."
    )
