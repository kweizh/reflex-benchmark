import os
import socket

import pytest
import requests
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/editor"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback (::1)
# while the dev server listens on the IPv4 loopback only, which would make the
# readiness check hang for the full timeout and raise a confusing TimeoutError.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend on 3000, backend on 8000) via uv."""

    class Starter(ProcessStarter):
        name = "reflex_editor"
        # Run every reflex command through uv so the project's virtual environment
        # (with reflex installed) is used.
        args = ["uv", "run", "reflex", "run"]
        # CRITICAL: set `env` as a class attribute here, NEVER inside `popen_kwargs`,
        # otherwise Popen raises "got multiple values for keyword argument 'env'".
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the Next.js frontend, which can take a few minutes.
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend must be listening on 8000 for websocket/state events.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, BACKEND_PORT)) != 0:
                    return False
            # Frontend must be listening on 3000.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
            # Confirm the HTTP server actually responds; the first request triggers
            # on-demand bundling, so allow a generous timeout.
            try:
                resp = requests.get(BASE_URL, timeout=30)
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
            all_lines = []
        new_lines = all_lines[printed_log_lines:]
        skipped = printed_log_lines
        printed_log_lines = len(all_lines)
        print(f"============================== [{tag}: Begin] Captured {Starter.name} logfile ==============================")
        if skipped > 0:
            print(f"(skipped {skipped} already-printed lines)")
        print("".join(new_lines))
        print(f"============================== [{tag}: End  ] Captured {Starter.name} logfile ==============================")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_initial_commit_undo_redo_flow(start_app, browser_verifier):
    reason = (
        "The editor must maintain server-side undo/redo history. Committing a value records the "
        "previous content on the undo stack and clears the redo stack; undo restores the previous "
        "value while moving the current value to the redo stack; redo re-applies it. The history "
        "label and the enabled/disabled state of the Undo/Redo buttons must reflect the stack depths."
    )
    truth = (
        f"Open a fresh browser session and navigate to {BASE_URL}. "
        "The page has a text input, a button labeled 'Commit', a button labeled 'Undo', a button "
        "labeled 'Redo', an element with id 'content-display' showing the current content, and an "
        "element with id 'history-label'. "
        "Step 1 (initial): Verify the 'content-display' element is empty, the 'history-label' text is "
        "exactly 'Undo depth: 0 | Redo depth: 0', and BOTH the 'Undo' and 'Redo' buttons are disabled. "
        "Step 2 (commits): Type 'alpha' into the input and click 'Commit'. Verify 'content-display' now "
        "shows 'alpha', 'history-label' is exactly 'Undo depth: 1 | Redo depth: 0', 'Undo' is enabled and "
        "'Redo' is disabled. Then commit 'beta', then commit 'gamma'. Verify 'content-display' shows "
        "'gamma' and 'history-label' is exactly 'Undo depth: 3 | Redo depth: 0'. "
        "Step 3 (undo): Click 'Undo'. Verify 'content-display' shows 'beta', 'history-label' is exactly "
        "'Undo depth: 2 | Redo depth: 1', and 'Redo' is now enabled. Click 'Undo' again. Verify "
        "'content-display' shows 'alpha' and 'history-label' is exactly 'Undo depth: 1 | Redo depth: 2'. "
        "Step 4 (redo): Click 'Redo'. Verify 'content-display' shows 'beta' and 'history-label' is exactly "
        "'Undo depth: 2 | Redo depth: 1'. "
        "Step 5 (commit clears redo): Type 'delta' into the input and click 'Commit'. Verify "
        "'content-display' shows 'delta', 'history-label' is exactly 'Undo depth: 3 | Redo depth: 0', and "
        "'Redo' is now disabled. "
        "Step 6 (undo to empty): Click 'Undo' repeatedly until the 'Undo' button becomes disabled. Verify "
        "that at that point 'content-display' is empty and 'history-label' is exactly "
        "'Undo depth: 0 | Redo depth: 3', with 'Undo' disabled and 'Redo' enabled. "
        "The verification passes only if every one of these observations holds."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_initial_commit_undo_redo_flow",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_bounded_history_depth(start_app, browser_verifier):
    reason = (
        "The undo history is bounded to at most 50 entries. Once more than 50 commits are made, the "
        "oldest entries are dropped so the undo depth never exceeds 50."
    )
    truth = (
        f"Open a fresh browser session and navigate to {BASE_URL} (start from empty history). "
        "Commit 55 different values one at a time by typing each value into the input and clicking the "
        "'Commit' button: use 'v1', 'v2', 'v3', and so on up to 'v55'. "
        "After all 55 commits, verify that the 'content-display' element shows 'v55'. "
        "Then read the element with id 'history-label' and verify its text is exactly "
        "'Undo depth: 50 | Redo depth: 0' — the reported undo depth must be exactly 50 (not 55), "
        "confirming the history was capped at 50 entries. "
        "The verification passes only if the undo depth is exactly 50 and the redo depth is 0."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_bounded_history_depth",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
