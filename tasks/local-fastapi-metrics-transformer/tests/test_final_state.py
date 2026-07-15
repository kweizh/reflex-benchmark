import os
import socket

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/metrics_app"
# Connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) on some setups while the servers listen on 127.0.0.1 only, which would
# make readiness checks hang for the full timeout.
HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"

METRICS_URL = f"{BACKEND_URL}/api/metrics"
INCREMENT_URL = f"{BACKEND_URL}/api/metrics/increment"

COUNTER_NAMES = ["page_view", "button_click", "api_call"]
TITLE_TEXT = "Live Metrics Dashboard"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex app fresh so in-process counters begin at 0."""

    class Starter(ProcessStarter):
        name = "reflex_app"
        # Run the app via the project's own uv-managed environment (reflex is
        # NOT installed in the system python). Pin ports to be explicit.
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
        # CRITICAL: set env as a class attribute, never inside popen_kwargs.
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the frontend; allow plenty of time.
        timeout = 900
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend must answer the reserved health route with "pong".
            if not _port_open(HOST, BACKEND_PORT):
                return False
            try:
                ping = requests.get(f"{BACKEND_URL}/ping/", timeout=20)
                if ping.status_code != 200 or "pong" not in ping.text:
                    return False
            except requests.RequestException:
                return False
            # Frontend must be serving as well.
            if not _port_open(HOST, FRONTEND_PORT):
                return False
            try:
                resp = requests.get(FRONTEND_URL, timeout=30)
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


def test_initial_metrics_snapshot(start_app):
    resp = requests.get(METRICS_URL, timeout=30)
    assert resp.status_code == 200, f"GET /api/metrics returned {resp.status_code}, expected 200."
    data = resp.json()
    assert set(data.keys()) == {"counters", "total"}, (
        f"GET /api/metrics must return exactly the keys 'counters' and 'total', got: {sorted(data.keys())}"
    )
    assert data["counters"] == {"page_view": 0, "button_click": 0, "api_call": 0}, (
        f"Expected all three counters to start at 0, got: {data['counters']}"
    )
    assert data["total"] == 0, f"Expected initial total 0, got: {data['total']}"


def test_increment_default_amount(start_app):
    resp = requests.post(INCREMENT_URL, json={"name": "page_view"}, timeout=30)
    assert resp.status_code == 200, (
        f"POST /api/metrics/increment for 'page_view' returned {resp.status_code}, expected 200."
    )
    assert resp.json() == {"name": "page_view", "value": 1, "total": 1}, (
        f"Expected {{'name': 'page_view', 'value': 1, 'total': 1}}, got: {resp.json()}"
    )


def test_increment_explicit_amount(start_app):
    resp = requests.post(INCREMENT_URL, json={"name": "api_call", "amount": 5}, timeout=30)
    assert resp.status_code == 200, (
        f"POST /api/metrics/increment for 'api_call' amount 5 returned {resp.status_code}, expected 200."
    )
    assert resp.json() == {"name": "api_call", "value": 5, "total": 6}, (
        f"Expected {{'name': 'api_call', 'value': 5, 'total': 6}}, got: {resp.json()}"
    )


def test_snapshot_reflects_increments(start_app):
    resp = requests.get(METRICS_URL, timeout=30)
    assert resp.status_code == 200, f"GET /api/metrics returned {resp.status_code}, expected 200."
    data = resp.json()
    assert data["counters"] == {"page_view": 1, "button_click": 0, "api_call": 5}, (
        f"Expected counters to reflect prior increments, got: {data['counters']}"
    )
    assert data["total"] == 6, f"Expected total 6 after increments, got: {data['total']}"


def test_unknown_counter_rejected(start_app):
    resp = requests.post(INCREMENT_URL, json={"name": "does_not_exist"}, timeout=30)
    assert resp.status_code == 404, (
        f"Incrementing an unknown counter must return 404, got: {resp.status_code}"
    )
    # Known counters must be unchanged.
    snapshot = requests.get(METRICS_URL, timeout=30).json()
    assert snapshot["total"] == 6, (
        f"Unknown-counter request must not change any counter; expected total still 6, got: {snapshot['total']}"
    )


def test_frontend_served(start_app):
    resp = requests.get(FRONTEND_URL, timeout=30)
    assert resp.status_code == 200, f"Frontend at {FRONTEND_URL} returned {resp.status_code}, expected 200."


def test_frontend_compiled_with_title(start_app):
    web_dir = os.path.join(PROJECT_DIR, ".web")
    assert os.path.isdir(web_dir), (
        f"Expected compiled frontend directory {web_dir} to exist after the app runs."
    )
    found = False
    for root, dirs, files in os.walk(web_dir):
        # Skip dependency dir to keep the scan fast.
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        for fname in files:
            if not fname.endswith((".js", ".jsx", ".ts", ".tsx", ".html")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    if TITLE_TEXT in f.read():
                        found = True
                        break
            except OSError:
                continue
        if found:
            break
    assert found, (
        f"Expected the string '{TITLE_TEXT}' to appear in the compiled frontend under {web_dir}, "
        "confirming the dashboard title/heading was implemented."
    )
