import os
import socket
import subprocess

import pytest
import requests
from pochi_verifier import PochiVerifier
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/optimistic_todo"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")

# Bind/connect over IPv4 explicitly to avoid IPv6 loopback (::1) resolution
# issues that can make readiness checks hang for the whole timeout.
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
BACKEND_PING_URL = f"http://{HOST}:{BACKEND_PORT}/ping"


def _query_db(sql):
    """Run a SQL statement against the app's SQLite database and return stdout.

    Returns None if the query fails (e.g. the table does not exist).
    """
    result = subprocess.run(
        ["sqlite3", "-batch", "-noheader", DB_PATH, sql],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server after resetting the todos table."""
    # Reset persisted todos so previous runs do not interfere. Ignore errors
    # (the file/table may not exist yet); a compliant app recreates the table.
    subprocess.run(
        ["sqlite3", DB_PATH, "DELETE FROM todoitem;"],
        capture_output=True,
        text=True,
    )

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            # Frontend port must be accepting connections.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
            # Backend must answer its ping endpoint.
            try:
                ping = requests.get(BACKEND_PING_URL, timeout=20)
                if ping.status_code >= 500:
                    return False
            except requests.RequestException:
                return False
            # The first request to the frontend triggers on-demand compilation,
            # which can take a while; allow a generous timeout.
            try:
                resp = requests.get(FRONTEND_URL, timeout=60)
                return resp.status_code < 500
            except requests.RequestException:
                return False

    info = xprocess.getinfo(Starter.name)
    printed_log_lines = 0

    def capture_logs(tag):
        nonlocal printed_log_lines
        try:
            with open(info.logpath, "r") as f:
                all_lines = f.readlines()
        except OSError:
            return
        new_lines = all_lines[printed_log_lines:]
        skipped = printed_log_lines
        printed_log_lines = len(all_lines)
        print(f"===================== [{tag}: Begin] {Starter.name} logfile =====================")
        if skipped > 0:
            print(f"(skipped {skipped} already-printed lines)")
        print("".join(new_lines))
        print(f"===================== [{tag}: End  ] {Starter.name} logfile =====================")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_optimistic_add_toggle_and_rollback(start_app, browser_verifier):
    """Add a normal todo, attempt a failing todo (rollback + error banner),
    toggle completion, and confirm persistence survives a reload."""
    reason = (
        "The app is an optimistic todo list. Adding a normal todo shows it "
        "immediately and persists it. Adding a todo whose title contains 'fail' "
        "must be rolled back with an error banner and never persisted. Toggling "
        "completion is persisted. Counts are shown live and successful changes "
        "survive a page reload."
    )
    truth = (
        f"Navigate to {FRONTEND_URL}. "
        "Confirm the todo list is empty and the counts read exactly 'Active: 0', "
        "'Completed: 0', and 'Total: 0', with no error banner shown. "
        "In the text input whose placeholder is 'New todo', type 'buy milk' and "
        "click the button labeled 'Add'. Verify that within a few seconds a todo "
        "item showing 'buy milk' appears, the counts become 'Active: 1', "
        "'Completed: 0', 'Total: 1', and no error banner is shown. "
        "Next type 'fail the build' into the same input and click 'Add'. Verify "
        "that an error banner appears whose text mentions 'fail the build', and "
        "that after a moment the list still shows only 'buy milk' with no item "
        "named 'fail the build', and the counts remain 'Active: 1', "
        "'Completed: 0', 'Total: 1'. "
        "Then click the checkbox on the 'buy milk' item to mark it complete and "
        "verify the counts become 'Active: 0', 'Completed: 1', 'Total: 1'. "
        f"Finally reload the page (navigate to {FRONTEND_URL} again) and verify "
        "that 'buy milk' is still present and shown as completed, that no item "
        "named 'fail the build' exists, and that the counts read 'Active: 0', "
        "'Completed: 1', 'Total: 1'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_optimistic_add_toggle_and_rollback",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_sqlite_has_only_successful_todo(start_app):
    """The SQLite table must contain only the successful, completed todo."""
    rows_out = _query_db("SELECT title, completed FROM todoitem;")
    assert rows_out is not None, (
        f"Could not read table 'todoitem' from {DB_PATH}. The app must persist "
        "todos in a SQLite table named 'todoitem'."
    )
    rows = [line for line in rows_out.splitlines() if line.strip()]
    assert len(rows) == 1, (
        f"Expected exactly one persisted todo, found {len(rows)}: {rows!r}"
    )
    title, _, completed = rows[0].partition("|")
    assert title.strip() == "buy milk", (
        f"Expected the persisted todo title to be 'buy milk', got {title!r}."
    )
    assert completed.strip() in ("1", "true", "True"), (
        f"Expected the persisted 'buy milk' todo to be completed (truthy), got {completed!r}."
    )

    fail_out = _query_db(
        "SELECT COUNT(*) FROM todoitem WHERE lower(title) LIKE '%fail%';"
    )
    assert fail_out is not None and fail_out.strip() == "0", (
        "A todo whose title contains 'fail' was persisted, but it must be rolled "
        f"back and never written to SQLite. Count was: {fail_out!r}"
    )


def test_delete_clears_list_and_db(start_app, browser_verifier):
    """Deleting the remaining todo empties both the UI and the database."""
    reason = (
        "Deleting a todo removes it from the visible list and from the SQLite "
        "database, and the empty state survives a reload."
    )
    truth = (
        f"Navigate to {FRONTEND_URL}. The list should show a single todo 'buy "
        "milk' that is marked complete. Click the button labeled 'Delete' on the "
        "'buy milk' item. Verify that the todo list becomes empty and the counts "
        "read exactly 'Active: 0', 'Completed: 0', and 'Total: 0'. Then reload "
        f"the page (navigate to {FRONTEND_URL} again) and confirm the list is "
        "still empty with all three counts equal to 0."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_delete_clears_list_and_db",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_sqlite_empty_after_delete(start_app):
    """After deletion the todos table must be empty."""
    count_out = _query_db("SELECT COUNT(*) FROM todoitem;")
    assert count_out is not None, (
        f"Could not read table 'todoitem' from {DB_PATH}."
    )
    assert count_out.strip() == "0", (
        f"Expected zero persisted todos after deletion, found: {count_out!r}"
    )
