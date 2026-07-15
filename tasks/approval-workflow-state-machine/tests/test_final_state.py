import os
import socket
import sqlite3
import subprocess

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/approval_app"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")

# Bind/connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) on some stacks, so servers may listen on ::1 only while an AF_INET socket
# to 127.0.0.1 never connects -> readiness checks would hang until timeout.
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """Invoke the workflow CLI inside the project's uv environment."""
    return subprocess.run(
        ["uv", "run", "python", "-m", "approval_app.workflow_cli", *args],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )


def parse_status(stdout: str):
    """Return (state, [allowed_actions]) parsed from `status` output."""
    state = None
    allowed = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("State:"):
            state = line[len("State:"):].strip()
        elif line.startswith("Allowed:"):
            rest = line[len("Allowed:"):].strip()
            allowed = [a.strip() for a in rest.split(",") if a.strip()]
    return state, allowed


def read_audit_rows():
    assert os.path.isfile(DB_PATH), f"SQLite database not found at {DB_PATH}."
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute(
            "SELECT from_state, to_state, action, timestamp "
            "FROM auditlogentry ORDER BY id"
        )
        return cur.fetchall()
    finally:
        con.close()


@pytest.fixture(scope="session")
def start_app(xprocess):
    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 420
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open(BACKEND_PORT):
                return False
            if not _port_open(FRONTEND_PORT):
                return False
            # Backend health endpoint.
            try:
                ping = requests.get(f"{BACKEND_URL}/ping", timeout=20)
                if ping.status_code >= 500:
                    return False
            except requests.RequestException:
                return False
            # Frontend served (first request triggers on-demand bundling).
            try:
                resp = requests.get(FRONTEND_URL, timeout=30)
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
            return
        new = lines[printed:]
        printed = len(lines)
        print(f"===== [{tag}] reflex_app log =====")
        print("".join(new))
        print(f"===== [{tag}] end reflex_app log =====")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_backend_ping(start_app):
    resp = requests.get(f"{BACKEND_URL}/ping", timeout=30)
    assert resp.status_code == 200, (
        f"Expected HTTP 200 from {BACKEND_URL}/ping, got {resp.status_code}."
    )
    assert "pong" in resp.text.lower(), (
        f"Expected 'pong' from backend /ping, got: {resp.text!r}"
    )


def test_frontend_serves(start_app):
    resp = requests.get(FRONTEND_URL, timeout=30)
    assert resp.status_code == 200, (
        f"Expected HTTP 200 from {FRONTEND_URL} (Reflex UI should compile and "
        f"serve), got {resp.status_code}."
    )


def test_workflow_state_machine_and_audit_log(start_app):
    # --- Clean start (truth: Setup / reset) ---
    r = run_cli("reset")
    assert r.returncode == 0, f"'reset' should exit 0, got {r.returncode}. stderr: {r.stderr}"

    # --- Step 2: initial status ---
    r = run_cli("status")
    assert r.returncode == 0, f"'status' failed: {r.stderr}"
    state, allowed = parse_status(r.stdout)
    assert state == "Draft", f"Initial state should be 'Draft', got {state!r}. stdout: {r.stdout!r}"
    assert "submit" in allowed, f"'submit' should be allowed from Draft, got {allowed}."
    assert set(allowed) == {"submit"}, (
        f"Only 'submit' should be allowed from Draft, got {allowed}."
    )

    # --- Step 3: illegal transition from Draft is rejected ---
    r = run_cli("apply", "approve")
    assert r.returncode == 1, (
        f"Illegal action 'approve' from Draft should exit 1, got {r.returncode}. stdout: {r.stdout!r}"
    )
    assert "ERROR" in r.stdout, f"Illegal action should print an ERROR message, got: {r.stdout!r}"

    r = run_cli("status")
    state, _ = parse_status(r.stdout)
    assert state == "Draft", f"State must remain 'Draft' after illegal action, got {state!r}."

    rows = read_audit_rows()
    assert len(rows) == 0, f"Illegal action must not add an audit row; found {len(rows)} rows: {rows}."

    # --- Step 4: legal happy path ---
    for action, frm, to in [
        ("submit", "Draft", "Submitted"),
        ("start_review", "Submitted", "UnderReview"),
        ("approve", "UnderReview", "Approved"),
    ]:
        r = run_cli("apply", action)
        assert r.returncode == 0, (
            f"Legal action '{action}' should exit 0, got {r.returncode}. stderr: {r.stderr}"
        )
        assert f"OK: {frm} -> {to}" in r.stdout, (
            f"Expected 'OK: {frm} -> {to}' for action '{action}', got: {r.stdout!r}"
        )

    # --- Step 5: terminal state ---
    r = run_cli("status")
    state, allowed = parse_status(r.stdout)
    assert state == "Approved", f"State should be 'Approved' after happy path, got {state!r}."
    assert allowed == [], f"'Approved' is terminal and should allow no actions, got {allowed}."

    r = run_cli("apply", "submit")
    assert r.returncode == 1, (
        f"Any action from terminal 'Approved' should exit 1, got {r.returncode}. stdout: {r.stdout!r}"
    )
    assert "ERROR" in r.stdout, f"Illegal action from Approved should print ERROR, got: {r.stdout!r}"

    r = run_cli("status")
    state, _ = parse_status(r.stdout)
    assert state == "Approved", f"State must remain 'Approved' after illegal action, got {state!r}."

    # --- Step 6: audit log persisted, ordered, append-only ---
    rows = read_audit_rows()
    assert len(rows) == 3, f"Expected exactly 3 audit rows after happy path, got {len(rows)}: {rows}."
    expected = [
        ("Draft", "Submitted", "submit"),
        ("Submitted", "UnderReview", "start_review"),
        ("UnderReview", "Approved", "approve"),
    ]
    for i, (frm, to, action) in enumerate(expected):
        assert rows[i][0] == frm, f"Audit row {i} from_state expected {frm!r}, got {rows[i][0]!r}."
        assert rows[i][1] == to, f"Audit row {i} to_state expected {to!r}, got {rows[i][1]!r}."
        assert rows[i][2] == action, f"Audit row {i} action expected {action!r}, got {rows[i][2]!r}."
        assert rows[i][3] not in (None, ""), f"Audit row {i} must have a non-empty timestamp, got {rows[i][3]!r}."

    # --- Step 7: reject / revise cycle ---
    r = run_cli("reset")
    assert r.returncode == 0, f"'reset' should exit 0, got {r.returncode}. stderr: {r.stderr}"

    for action, frm, to in [
        ("submit", "Draft", "Submitted"),
        ("start_review", "Submitted", "UnderReview"),
        ("reject", "UnderReview", "Rejected"),
    ]:
        r = run_cli("apply", action)
        assert r.returncode == 0, f"Legal action '{action}' should exit 0, got {r.returncode}. stderr: {r.stderr}"
        assert f"OK: {frm} -> {to}" in r.stdout, (
            f"Expected 'OK: {frm} -> {to}' for action '{action}', got: {r.stdout!r}"
        )

    r = run_cli("status")
    state, allowed = parse_status(r.stdout)
    assert state == "Rejected", f"State should be 'Rejected', got {state!r}."
    assert "revise" in allowed, f"'revise' should be allowed from Rejected, got {allowed}."

    r = run_cli("apply", "revise")
    assert r.returncode == 0, f"Legal action 'revise' should exit 0, got {r.returncode}. stderr: {r.stderr}"
    assert "OK: Rejected -> Draft" in r.stdout, (
        f"Expected 'OK: Rejected -> Draft' for 'revise', got: {r.stdout!r}"
    )

    r = run_cli("status")
    state, _ = parse_status(r.stdout)
    assert state == "Draft", f"State should be back to 'Draft' after revise, got {state!r}."

    rows = read_audit_rows()
    assert len(rows) == 4, (
        f"After reset and the reject/revise cycle, expected 4 audit rows, got {len(rows)}: {rows}."
    )
