import os
import socket
import subprocess
import time

import pytest
import requests
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/email_scheduler"
SERVER_LOG = os.path.join(PROJECT_DIR, "server.log")
BACKEND_PORT = 8000
BASE_URL = f"http://127.0.0.1:{BACKEND_PORT}"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_ping(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/ping", timeout=2)
            if r.status_code == 200 and "pong" in r.text.lower():
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(1.0)
    raise RuntimeError(
        f"Reflex backend did not become ready on {BASE_URL}/ping within {timeout}s: {last_err}"
    )


def _safe_stop() -> None:
    try:
        requests.post(f"{BASE_URL}/api/scheduler/stop", json={}, timeout=5)
    except Exception:  # noqa: BLE001
        pass


def _seed(digests: list) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/scheduler/seed",
        json={"digests": digests},
        timeout=10,
    )
    assert r.status_code == 200, f"POST /api/scheduler/seed returned {r.status_code}: {r.text}"
    return r.json()


def _status() -> dict:
    r = requests.get(f"{BASE_URL}/api/scheduler/status", timeout=5)
    assert r.status_code == 200, f"GET /api/scheduler/status returned {r.status_code}: {r.text}"
    try:
        return r.json()
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"GET /api/scheduler/status returned non-JSON body: {r.text}") from e


def _sent() -> list:
    r = requests.get(f"{BASE_URL}/api/scheduler/sent", timeout=5)
    assert r.status_code == 200, f"GET /api/scheduler/sent returned {r.status_code}: {r.text}"
    body = r.json()
    assert isinstance(body, dict) and "rows" in body, (
        f"GET /api/scheduler/sent must return an object with a `rows` list, got {body}"
    )
    return body["rows"]


@pytest.fixture(scope="session", autouse=True)
def _kill_leftover_servers():
    # Make sure nothing else is bound to port 8000 before we start.
    subprocess.run(["pkill", "-f", "reflex run"], check=False)
    time.sleep(1.0)
    yield
    subprocess.run(["pkill", "-f", "reflex run"], check=False)


@pytest.fixture(scope="session")
def reflex_server(xprocess, _kill_leftover_servers):
    # Reset any stale log so the ImmutableStateError grep is meaningful.
    if os.path.exists(SERVER_LOG):
        try:
            os.remove(SERVER_LOG)
        except OSError:
            pass

    class Starter(ProcessStarter):
        name = "reflex_backend"
        args = [
            "uv", "run", "reflex", "run",
            "--backend-only",
            "--backend-port", str(BACKEND_PORT),
            "--loglevel", "debug",
        ]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 240
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open(BACKEND_PORT):
                return False
            try:
                r = requests.get(f"{BASE_URL}/ping", timeout=2)
                return r.status_code == 200 and "pong" in r.text.lower()
            except Exception:  # noqa: BLE001
                return False

    xprocess.ensure(Starter.name, Starter)
    _wait_for_ping(timeout=60.0)

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    # Defensive: nuke anything still bound.
    subprocess.run(["pkill", "-f", "reflex run"], check=False)


# ---------------------------------------------------------------------------
# 1. Source-code contract checks.
# ---------------------------------------------------------------------------

def _all_py_sources() -> str:
    blob_parts = []
    for root, _dirs, files in os.walk(PROJECT_DIR):
        if any(part in {".venv", "node_modules", ".web", "__pycache__"} for part in root.split(os.sep)):
            continue
        for name in files:
            if name.endswith(".py"):
                p = os.path.join(root, name)
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        blob_parts.append(f.read())
                except OSError:
                    pass
    return "\n\n".join(blob_parts)


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist; the executor must create the Reflex project there."
    )


def test_source_uses_background_event_decorator():
    src = _all_py_sources()
    assert "@rx.event(background=True)" in src, (
        "Expected at least one Python source file under /home/user/email_scheduler to declare "
        "an event handler with `@rx.event(background=True)`."
    )


def test_source_uses_state_lock_block():
    src = _all_py_sources()
    assert "async with self" in src, (
        "Expected at least one Python source file to enter the Reflex state lock with "
        "`async with self` (required to avoid ImmutableStateError in background tasks)."
    )


def test_source_declares_emaildigest_model():
    src = _all_py_sources()
    assert "class EmailDigest" in src, (
        "Expected the project to declare a `class EmailDigest` rx.Model for the digests table."
    )


def test_source_declares_sentemail_model():
    src = _all_py_sources()
    assert "class SentEmail" in src, (
        "Expected the project to declare a `class SentEmail` rx.Model for the sent-emails audit table."
    )


# ---------------------------------------------------------------------------
# 2. Behavioural verification via the FastAPI control endpoints.
# ---------------------------------------------------------------------------


def test_status_endpoint_initial_shape(reflex_server):
    _safe_stop()
    time.sleep(0.5)
    _seed([])
    snap = _status()
    for key in ("running", "now", "due_count", "queued_count", "total_sent"):
        assert key in snap, f"Status payload missing required key '{key}': {snap}"
    assert isinstance(snap["running"], bool), f"`running` must be a bool, got {snap}"
    assert isinstance(snap["now"], (int, float)), f"`now` must be a number, got {snap}"
    assert isinstance(snap["due_count"], int), f"`due_count` must be an int, got {snap}"
    assert isinstance(snap["queued_count"], int), f"`queued_count` must be an int, got {snap}"
    assert isinstance(snap["total_sent"], int), f"`total_sent` must be an int, got {snap}"
    assert snap["due_count"] == 0, f"After empty seed, due_count must be 0, got {snap}"
    assert snap["queued_count"] == 0, f"After empty seed, queued_count must be 0, got {snap}"
    assert snap["total_sent"] == 0, f"After empty seed, total_sent must be 0, got {snap}"


def test_bounded_throughput_for_two_second_period(reflex_server):
    _safe_stop()
    time.sleep(0.5)

    seed_resp = _seed([
        {
            "recipient": "alice@example.com",
            "period_seconds": 2,
            "first_due_in_seconds": 0.0,
        }
    ])
    assert seed_resp.get("seeded") == 1, f"Expected `seeded: 1`, got {seed_resp}"

    start = requests.post(f"{BASE_URL}/api/scheduler/start", json={}, timeout=5)
    assert start.status_code == 200, f"POST /api/scheduler/start returned {start.status_code}: {start.text}"
    assert start.json().get("running") is True, f"Expected `running: true` from /start, got {start.text}"

    # Let the scheduler run ~6 seconds.
    time.sleep(6.2)

    stop = requests.post(f"{BASE_URL}/api/scheduler/stop", json={}, timeout=5)
    assert stop.status_code == 200, f"POST /api/scheduler/stop returned {stop.status_code}: {stop.text}"
    assert stop.json().get("running") is False, f"Expected `running: false` from /stop, got {stop.text}"

    rows = [r for r in _sent() if r.get("recipient") == "alice@example.com"]
    count = len(rows)
    assert 2 <= count <= 4, (
        f"With period_seconds=2 over ~6s, expected between 2 and 4 SentEmail rows for alice, got {count} "
        f"(rows={rows})."
    )

    # No-duplicate-per-tick property: consecutive sends for the same digest must be at least
    # period_seconds - 0.5 apart, i.e. >= 1.5s with period_seconds=2.
    rows_sorted = sorted(rows, key=lambda r: r["sent_at"])
    for prev, curr in zip(rows_sorted, rows_sorted[1:]):
        gap = float(curr["sent_at"]) - float(prev["sent_at"])
        assert gap >= 1.5, (
            f"Consecutive sends for the same digest must be at least 1.5s apart "
            f"(period_seconds=2, tolerance 0.5); got gap={gap}s between {prev} and {curr}."
        )


def test_force_run_sends_immediately_when_not_due(reflex_server):
    _safe_stop()
    time.sleep(0.5)

    seed_resp = _seed([
        {
            "recipient": "bob@example.com",
            "period_seconds": 60,
            "first_due_in_seconds": 60.0,
        }
    ])
    assert seed_resp.get("seeded") == 1, f"Expected `seeded: 1`, got {seed_resp}"

    pre = _status()
    assert pre["due_count"] == 0, f"Bob should not be due yet; got status {pre}"
    assert pre["queued_count"] == 1, f"Bob should be queued; got status {pre}"
    assert pre["total_sent"] == 0, f"No sends yet; got status {pre}"

    t0 = time.time()
    force = requests.post(f"{BASE_URL}/api/scheduler/force_run", json={}, timeout=5)
    assert force.status_code == 200, f"POST /api/scheduler/force_run returned {force.status_code}: {force.text}"
    fbody = force.json()
    assert fbody.get("sent") == 1, f"Expected `sent: 1` from force_run, got {fbody}"
    assert fbody.get("recipient") == "bob@example.com", (
        f"Expected force_run to target bob@example.com, got {fbody}"
    )
    assert isinstance(fbody.get("digest_id"), int), f"force_run must return an integer digest_id, got {fbody}"

    rows = [r for r in _sent() if r.get("recipient") == "bob@example.com"]
    assert len(rows) == 1, f"Force Run should produce exactly one SentEmail row for bob, got {rows}"
    sent_at = float(rows[0]["sent_at"])
    assert abs(sent_at - t0) <= 2.0, (
        f"Force Run should record sent_at within ~2s of the call; got sent_at={sent_at}, t0={t0} (delta={sent_at - t0})."
    )

    post = _status()
    assert post["total_sent"] == 1, f"After force_run, total_sent must be 1, got {post}"
    assert post["due_count"] == 0, (
        f"Force Run must reschedule the digest forward by period_seconds; due_count should be 0, got {post}"
    )
    assert post["queued_count"] == 1, (
        f"After Force Run, bob's digest should still be queued (just rescheduled), got {post}"
    )


def test_idempotent_restart(reflex_server):
    _safe_stop()
    time.sleep(0.5)
    _seed([])

    s1 = requests.post(f"{BASE_URL}/api/scheduler/start", json={}, timeout=5)
    assert s1.status_code == 200, f"First /start returned {s1.status_code}: {s1.text}"
    assert s1.json().get("running") is True

    s2 = requests.post(f"{BASE_URL}/api/scheduler/start", json={}, timeout=5)
    assert s2.status_code == 200, f"Second /start returned {s2.status_code}: {s2.text}"
    assert s2.json().get("running") is True, "Idempotent restart must still report running=true"

    snap = _status()
    assert snap["running"] is True, f"After two starts, status must still report running=true, got {snap}"

    stop = requests.post(f"{BASE_URL}/api/scheduler/stop", json={}, timeout=5)
    assert stop.status_code == 200, f"POST /api/scheduler/stop returned {stop.status_code}: {stop.text}"

    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        snap = _status()
        if snap.get("running") is False:
            final = snap
            break
        time.sleep(0.1)
    assert final is not None, (
        "Scheduler did not report `running=false` within 2 seconds of /stop after an idempotent restart."
    )


def test_no_immutable_state_error_in_logs(reflex_server):
    # Give the server a beat to flush logs from the prior tests.
    time.sleep(0.3)
    assert os.path.isfile(SERVER_LOG), (
        f"Expected server log at {SERVER_LOG} (start command must redirect stdout/stderr there)."
    )
    with open(SERVER_LOG, "r", encoding="utf-8", errors="replace") as f:
        contents = f.read()
    assert "ImmutableStateError" not in contents, (
        "Server log contains `ImmutableStateError`; the background task is mutating state "
        "outside an `async with self` block."
    )
