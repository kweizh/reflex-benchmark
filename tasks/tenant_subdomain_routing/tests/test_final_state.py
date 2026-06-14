import os
import socket
import time

import pytest
import requests
from pochi_verifier import PochiVerifier
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/myproject"
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def _wait_for_backend_ping(timeout: float = 240.0) -> None:
    deadline = time.time() + timeout
    last_error: str | None = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{BACKEND_URL}/ping", timeout=2)
            if r.status_code == 200 and r.text.strip().strip('"') == "pong":
                return
            last_error = f"ping status={r.status_code}, body={r.text!r}"
        except requests.RequestException as e:
            last_error = str(e)
        time.sleep(2.0)
    raise AssertionError(
        f"Backend did not become healthy on {BACKEND_URL}/ping within {timeout:.0f}s; last error: {last_error}"
    )


def _wait_for_frontend(timeout: float = 240.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open("localhost", 3000):
            return
        time.sleep(2.0)
    raise AssertionError(
        f"Frontend did not become reachable on port 3000 within {timeout:.0f}s."
    )


@pytest.fixture(scope="session")
def reflex_server(xprocess):
    class Starter(ProcessStarter):
        name = "reflex_server"
        args = ["uv", "run", "reflex", "run", "--env", "prod"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            try:
                r = requests.get(f"{BACKEND_URL}/ping", timeout=2)
                if r.status_code != 200:
                    return False
                if r.text.strip().strip('"') != "pong":
                    return False
            except requests.RequestException:
                return False
            return _port_open("localhost", 3000)

    xprocess.ensure(Starter.name, Starter)

    # Belt-and-suspenders explicit readiness wait.
    _wait_for_backend_ping()
    _wait_for_frontend()

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()


@pytest.fixture(scope="session")
def browser_verifier(reflex_server):
    yield PochiVerifier()


def test_backend_ping_returns_pong(reflex_server):
    r = requests.get(f"{BACKEND_URL}/ping", timeout=5)
    assert r.status_code == 200, (
        f"Expected GET /ping to return 200 but got {r.status_code}: {r.text!r}"
    )
    assert r.text.strip().strip('"') == "pong", (
        f"Expected GET /ping body to be \"pong\" but got: {r.text!r}"
    )


def test_dashboard_renders_acme(browser_verifier):
    reason = (
        "The page /t/[tenant_id]/dashboard should load the matching tenant via the Reflex router "
        "dynamic segment, display the tenant's name, and clearly identify itself as the Dashboard page."
    )
    truth = (
        "Navigate to http://localhost:3000/t/acme/dashboard. Wait for the page to finish loading and "
        "hydrating. The visible page MUST contain the text 'Acme Corp' AND the text 'Dashboard'. The page "
        "MUST NOT contain the text 'Tenant Not Found'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_dashboard_renders_acme",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_settings_renders_globex(browser_verifier):
    reason = (
        "The page /t/[tenant_id]/settings should load the matching tenant via the Reflex router "
        "dynamic segment and clearly identify itself as the Settings page."
    )
    truth = (
        "Navigate to http://localhost:3000/t/globex/settings. Wait for the page to finish loading and "
        "hydrating. The visible page MUST contain the text 'Globex Inc' AND the text 'Settings'. The page "
        "MUST NOT contain the text 'Tenant Not Found'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_settings_renders_globex",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_dashboard_renders_initech(browser_verifier):
    reason = (
        "The third seed tenant 'initech' should be reachable via the dashboard dynamic route and display its name."
    )
    truth = (
        "Navigate to http://localhost:3000/t/initech/dashboard. Wait for the page to finish loading and "
        "hydrating. The visible page MUST contain the text 'Initech LLC' AND the text 'Dashboard'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_dashboard_renders_initech",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_unknown_tenant_renders_404_marker(browser_verifier):
    reason = (
        "When the dynamic tenant_id does not match any Tenant row, the page should render an rx.cond-controlled "
        "404 marker instead of leaking any other tenant's information."
    )
    truth = (
        "Navigate to http://localhost:3000/t/no-such-tenant/dashboard. Wait for the page to finish loading and "
        "hydrating. The visible page MUST contain the text 'Tenant Not Found'. The page MUST NOT contain any of "
        "'Acme Corp', 'Globex Inc', or 'Initech LLC'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_unknown_tenant_renders_404_marker",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_api_me_succeeds_for_acme(reflex_server):
    r = requests.get(
        f"{BACKEND_URL}/api/me",
        headers={"X-Tenant-Id": "acme"},
        timeout=10,
    )
    assert r.status_code == 200, (
        f"Expected /api/me with X-Tenant-Id=acme to return 200 but got {r.status_code}: {r.text!r}"
    )
    body = r.json()
    assert body == {"slug": "acme", "name": "Acme Corp"}, (
        f"Expected /api/me body to equal {{'slug': 'acme', 'name': 'Acme Corp'}} but got {body!r}"
    )


def test_api_me_succeeds_for_initech(reflex_server):
    r = requests.get(
        f"{BACKEND_URL}/api/me",
        headers={"X-Tenant-Id": "initech"},
        timeout=10,
    )
    assert r.status_code == 200, (
        f"Expected /api/me with X-Tenant-Id=initech to return 200 but got {r.status_code}: {r.text!r}"
    )
    body = r.json()
    assert body == {"slug": "initech", "name": "Initech LLC"}, (
        f"Expected /api/me body to equal {{'slug': 'initech', 'name': 'Initech LLC'}} but got {body!r}"
    )


def test_api_me_rejects_missing_header(reflex_server):
    r = requests.get(f"{BACKEND_URL}/api/me", timeout=10)
    assert r.status_code == 403, (
        f"Expected /api/me with no header to return 403 but got {r.status_code}: {r.text!r}"
    )
    body = r.json()
    assert body == {"detail": "forbidden"}, (
        f"Expected /api/me 403 body to equal {{'detail': 'forbidden'}} but got {body!r}"
    )


def test_api_me_rejects_unknown_tenant(reflex_server):
    r = requests.get(
        f"{BACKEND_URL}/api/me",
        headers={"X-Tenant-Id": "not-a-tenant"},
        timeout=10,
    )
    assert r.status_code == 403, (
        f"Expected /api/me with unknown tenant to return 403 but got {r.status_code}: {r.text!r}"
    )
    body = r.json()
    assert body == {"detail": "forbidden"}, (
        f"Expected /api/me 403 body to equal {{'detail': 'forbidden'}} but got {body!r}"
    )
