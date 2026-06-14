import json
import os
import socket
import subprocess
import time

import pytest
import requests
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/streaming_chat"
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


def _safe_cancel() -> None:
    try:
        requests.post(f"{BASE_URL}/api/chat/cancel", json={}, timeout=5)
    except Exception:  # noqa: BLE001
        pass


def _get_status() -> dict:
    r = requests.get(f"{BASE_URL}/api/chat/status", timeout=5)
    assert r.status_code == 200, f"GET /api/chat/status returned {r.status_code}: {r.text}"
    try:
        return r.json()
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"GET /api/chat/status returned non-JSON body: {r.text}") from e


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
# 1. Source-code contract checks (do not require the server to be running).
# ---------------------------------------------------------------------------

def _all_py_sources() -> str:
    blob_parts = []
    for root, _dirs, files in os.walk(PROJECT_DIR):
        # Skip vendored/virtualenv directories.
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
        "Expected at least one Python source file under /home/user/streaming_chat to declare "
        "an event handler with `@rx.event(background=True)`."
    )


def test_source_uses_state_lock_block():
    src = _all_py_sources()
    assert "async with self" in src, (
        "Expected at least one Python source file to enter the Reflex state lock with "
        "`async with self` (required to avoid ImmutableStateError in background tasks)."
    )


def test_source_declares_backend_only_streaming_flag():
    src = _all_py_sources()
    assert "_is_streaming" in src, (
        "Expected the state class to declare a backend-only `_is_streaming` flag "
        "(identifier starting with an underscore so it is not synchronized to the client)."
    )


def test_source_declares_backend_only_cancel_flag():
    src = _all_py_sources()
    assert "_should_cancel" in src, (
        "Expected the state class to declare a backend-only `_should_cancel` flag "
        "observed by the background task between yields."
    )


# ---------------------------------------------------------------------------
# 2. Behavioural verification via the FastAPI control endpoints.
# ---------------------------------------------------------------------------


def test_status_endpoint_initial_shape(reflex_server):
    _safe_cancel()
    time.sleep(0.4)
    snap = _get_status()
    for key in ("is_streaming", "current_response", "chunks_streamed", "was_cancelled", "completed"):
        assert key in snap, f"Status payload missing required key '{key}': {snap}"
    assert isinstance(snap["is_streaming"], bool), f"`is_streaming` must be a bool, got {snap}"
    assert isinstance(snap["current_response"], str), f"`current_response` must be a string, got {snap}"
    assert isinstance(snap["chunks_streamed"], int), f"`chunks_streamed` must be an int, got {snap}"
    assert isinstance(snap["was_cancelled"], bool), f"`was_cancelled` must be a bool, got {snap}"
    assert isinstance(snap["completed"], bool), f"`completed` must be a bool, got {snap}"


def test_uninterrupted_stream_completes_with_enough_chunks(reflex_server):
    _safe_cancel()
    time.sleep(0.4)

    send = requests.post(
        f"{BASE_URL}/api/chat/send",
        json={"prompt": "explain reflex background events"},
        timeout=5,
    )
    assert send.status_code == 200, f"POST /api/chat/send returned {send.status_code}: {send.text}"
    body = send.json()
    assert body.get("accepted") is True, f"Expected `accepted: true` in /api/chat/send response, got {body}"

    saw_streaming_true = False
    final = None
    deadline = time.time() + 15.0
    while time.time() < deadline:
        snap = _get_status()
        if snap.get("is_streaming") is True:
            saw_streaming_true = True
        if snap.get("completed") is True and snap.get("is_streaming") is False:
            final = snap
            break
        time.sleep(0.25)

    assert final is not None, (
        "Stream did not reach `completed=true` and `is_streaming=false` within 15 seconds."
    )
    assert saw_streaming_true, (
        "Expected `is_streaming` to be true at least once during the uninterrupted stream "
        "(loading state never transitioned through True)."
    )
    assert final["was_cancelled"] is False, (
        f"Uninterrupted run should have `was_cancelled=false`, got {final}"
    )
    assert final["chunks_streamed"] >= 12, (
        f"Uninterrupted run should yield at least 12 chunks, got {final['chunks_streamed']} (full snapshot: {final})."
    )
    assert final["current_response"], (
        f"Uninterrupted run should leave a non-empty `current_response`, got {final}"
    )


def test_cancellation_stops_stream_promptly(reflex_server):
    _safe_cancel()
    time.sleep(0.4)

    send = requests.post(
        f"{BASE_URL}/api/chat/send",
        json={"prompt": "a long story please"},
        timeout=5,
    )
    assert send.status_code == 200, f"POST /api/chat/send returned {send.status_code}: {send.text}"

    # Give the stream a moment to publish a few chunks.
    time.sleep(0.4)
    pre_cancel = _get_status()
    chunks_at_cancel = int(pre_cancel.get("chunks_streamed", 0))

    cancel = requests.post(f"{BASE_URL}/api/chat/cancel", json={}, timeout=5)
    assert cancel.status_code == 200, f"POST /api/chat/cancel returned {cancel.status_code}: {cancel.text}"
    cancel_body = cancel.json()
    assert cancel_body.get("cancelled") is True, (
        f"Expected `cancelled: true` in /api/chat/cancel response, got {cancel_body}"
    )

    deadline = time.time() + 1.0
    final = None
    while time.time() < deadline:
        snap = _get_status()
        if snap.get("is_streaming") is False:
            final = snap
            break
        time.sleep(0.05)

    assert final is not None, (
        "Background task did not observe the cancel flag within 1 second of /api/chat/cancel."
    )
    assert final["was_cancelled"] is True, (
        f"Cancelled run should have `was_cancelled=true`, got {final}"
    )
    assert final["is_streaming"] is False, (
        f"Cancelled run should have `is_streaming=false` shortly after cancel, got {final}"
    )

    extra_chunks = int(final["chunks_streamed"]) - chunks_at_cancel
    assert extra_chunks <= 2, (
        f"Cancellation should be observed between yields with a bounded delay; "
        f"emitted {extra_chunks} extra chunks after cancel (pre={chunks_at_cancel}, final={final})."
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
