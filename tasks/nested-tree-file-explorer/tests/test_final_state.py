import os
import socket

import pytest
import requests
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/tree_explorer"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) on some stacks, which would make the readiness check hang for the full
# timeout even though the server is listening on 127.0.0.1.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend on 3000, backend on 8000).

    The first `reflex run` compiles the Next.js frontend and installs the JS
    toolchain, which can take several minutes, so the startup timeout is
    intentionally generous.
    """

    class Starter(ProcessStarter):
        name = "reflex_app"
        # Run through uv so the project's isolated environment (with reflex
        # installed) is used. Pin the ports so the readiness check matches.
        args = [
            "uv",
            "run",
            "reflex",
            "run",
            "--frontend-port",
            str(FRONTEND_PORT),
            "--backend-port",
            str(BACKEND_PORT),
        ]
        # CRITICAL: set `env` as a class attribute here, never inside
        # `popen_kwargs`, otherwise Popen raises a duplicate-keyword TypeError.
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
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
        except FileNotFoundError:
            all_lines = []
        new_lines = all_lines[printed_log_lines:]
        skipped = printed_log_lines
        printed_log_lines = len(all_lines)
        print(f"===================== [{tag}: Begin] Captured {Starter.name} logfile =====================")
        if skipped > 0:
            print(f"(skipped {skipped} already-printed lines)")
        print("".join(new_lines))
        print(f"===================== [{tag}: End  ] Captured {Starter.name} logfile =====================")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_initial_render_and_total_count(start_app, browser_verifier):
    reason = (
        "On first load the explorer must show only the root folder expanded, "
        "displaying its direct children, and must report the total number of files."
    )
    truth = (
        f"Navigate to {BASE_URL} and wait for the page to fully load. "
        "Verify the page contains the exact text 'Total files: 5'. "
        "Verify the nodes 'src', 'docs', and 'README.md' are visible. "
        "Verify the nodes 'app.py', 'utils', 'helpers.py', 'math.py', and 'guide.md' "
        "are NOT visible (their parent folders are collapsed by default). "
        "Verify the page shows the exact text 'No file selected' because nothing is selected yet."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_initial_render_and_total_count",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_expand_folders_and_select_deep_file(start_app, browser_verifier):
    reason = (
        "Expanding folders must reveal their children, and selecting a deeply nested "
        "file must show its full breadcrumb path."
    )
    truth = (
        f"Navigate to {BASE_URL} and wait for the page to fully load. "
        "Click the node labeled 'src'. Verify that 'app.py' and 'utils' become visible, "
        "while 'helpers.py' and 'math.py' are still not visible. "
        "Then click the node labeled 'utils'. Verify that 'helpers.py' and 'math.py' become visible. "
        "Then click the node labeled 'helpers.py'. "
        "Verify the page now shows the exact breadcrumb text 'root / src / utils / helpers.py'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_expand_folders_and_select_deep_file",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_select_shallow_file(start_app, browser_verifier):
    reason = "Selecting a file directly under the root must show a two-segment breadcrumb."
    truth = (
        f"Navigate to {BASE_URL} and wait for the page to fully load. "
        "Click the node labeled 'README.md'. "
        "Verify the page shows the exact breadcrumb text 'root / README.md'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_select_shallow_file",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_expand_docs_and_select_file(start_app, browser_verifier):
    reason = "Expanding the docs folder and selecting its file must show the correct breadcrumb."
    truth = (
        f"Navigate to {BASE_URL} and wait for the page to fully load. "
        "Click the node labeled 'docs'. Verify that 'guide.md' becomes visible. "
        "Then click the node labeled 'guide.md'. "
        "Verify the page shows the exact breadcrumb text 'root / docs / guide.md'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_expand_docs_and_select_file",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_collapse_hides_descendants(start_app, browser_verifier):
    reason = "Collapsing an expanded folder must hide all of its descendants."
    truth = (
        f"Navigate to {BASE_URL} and wait for the page to fully load. "
        "Click the node labeled 'src' to expand it and verify 'app.py' and 'utils' become visible. "
        "Click the node labeled 'utils' to expand it and verify 'helpers.py' and 'math.py' become visible. "
        "Now click the node labeled 'src' again to collapse it. "
        "Verify that 'app.py', 'utils', 'helpers.py', and 'math.py' are all no longer visible."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_collapse_hides_descendants",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
