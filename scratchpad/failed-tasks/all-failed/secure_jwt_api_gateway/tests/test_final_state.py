import os
import socket
import subprocess
import time

import jwt
import pytest
import requests
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/secure_jwt_api_gateway"
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

USERNAME = "alice_h4k9m2"
PASSWORD = "P@ssw0rd_X9zL2qN8"
JWT_SECRET = "9f3e8a1c4b7d2e5f8a0b3c6d9e2f1a4b7c0d3e6f9a2b5c8d1e4f7a0b3c6d9e2f"


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


@pytest.fixture(scope="session")
def reflex_server(xprocess):
    """Start the Reflex app once for the session and tear it down at the end."""
    # Free ports before starting in case a stale process is still bound.
    _kill_servers()
    time.sleep(2)

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend (with mounted FastAPI routes) must be live AND
            # the frontend must be reachable.
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
    # Hard cleanup in case xprocess termination misses child processes.
    _kill_servers()


def test_backend_ping_route_alive(reflex_server):
    """The Reflex backend reserved `/ping` route must answer 'pong'."""
    response = requests.get(f"{BACKEND_URL}/ping", timeout=5)
    assert response.status_code == 200, (
        f"Expected 200 from {BACKEND_URL}/ping, got {response.status_code}"
    )
    assert "pong" in response.text.lower(), (
        f"Expected 'pong' in /ping response body, got {response.text!r}"
    )


def test_login_success_returns_valid_jwt(reflex_server):
    """POST /auth/login with the correct credentials returns a JWT signed with HS256."""
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    assert response.status_code == 200, (
        f"Expected 200 from /auth/login with valid credentials, "
        f"got {response.status_code}: body={response.text!r}"
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise AssertionError(
            f"/auth/login did not return JSON. Body={response.text!r}"
        ) from exc
    assert isinstance(payload, dict), (
        f"/auth/login JSON body must be an object, got {type(payload).__name__}"
    )
    assert "access_token" in payload, (
        f"/auth/login response missing 'access_token' key. Body={payload!r}"
    )
    token = payload["access_token"]
    assert isinstance(token, str) and token, (
        f"'access_token' must be a non-empty string, got {token!r}"
    )
    assert payload.get("token_type") == "bearer", (
        f"Expected token_type=='bearer', got {payload.get('token_type')!r}"
    )

    decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    assert decoded.get("sub") == USERNAME, (
        f"JWT 'sub' claim must equal {USERNAME!r}, got {decoded.get('sub')!r}"
    )


def test_login_failure_returns_401(reflex_server):
    """POST /auth/login with a wrong password returns HTTP 401."""
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": USERNAME, "password": "wrong_password"},
        timeout=10,
    )
    assert response.status_code == 401, (
        f"Expected 401 from /auth/login with wrong password, "
        f"got {response.status_code}: body={response.text!r}"
    )


def test_me_with_valid_token_returns_username(reflex_server):
    """GET /auth/me with a valid Bearer token returns the username."""
    login = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    assert login.status_code == 200, (
        f"Pre-step /auth/login failed: {login.status_code} {login.text!r}"
    )
    token = login.json()["access_token"]

    response = requests.get(
        f"{BACKEND_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert response.status_code == 200, (
        f"Expected 200 from /auth/me with valid bearer token, "
        f"got {response.status_code}: body={response.text!r}"
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise AssertionError(
            f"/auth/me did not return JSON. Body={response.text!r}"
        ) from exc
    assert body.get("username") == USERNAME, (
        f"/auth/me must return username={USERNAME!r}, got {body!r}"
    )


def test_me_without_token_rejected(reflex_server):
    """GET /auth/me without an Authorization header is rejected with 401."""
    response = requests.get(f"{BACKEND_URL}/auth/me", timeout=10)
    assert response.status_code == 401, (
        f"Expected 401 from /auth/me without auth header, "
        f"got {response.status_code}: body={response.text!r}"
    )


def test_me_with_tampered_token_rejected(reflex_server):
    """GET /auth/me with a JWT signed by a different secret is rejected with 401."""
    forged_token = jwt.encode(
        {"sub": USERNAME},
        "not-the-real-secret",
        algorithm="HS256",
    )
    response = requests.get(
        f"{BACKEND_URL}/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
        timeout=10,
    )
    assert response.status_code == 401, (
        f"Expected 401 from /auth/me with a forged token, "
        f"got {response.status_code}: body={response.text!r}"
    )


def test_frontend_root_page_has_login_text(reflex_server):
    """GET / returns 200 and contains the visible 'Login' label."""
    response = requests.get(f"{FRONTEND_URL}/", timeout=15)
    assert response.status_code == 200, (
        f"Expected 200 from {FRONTEND_URL}/, got {response.status_code}"
    )
    assert "Login" in response.text, (
        "Expected the rendered root page HTML to contain the visible 'Login' "
        "label that triggers the auth flow."
    )


def test_frontend_does_not_leak_secret_or_password(reflex_server):
    """The compiled root page HTML must not expose the JWT secret or the password."""
    response = requests.get(f"{FRONTEND_URL}/", timeout=15)
    assert response.status_code == 200, (
        f"Expected 200 from {FRONTEND_URL}/, got {response.status_code}"
    )
    html = response.text
    assert JWT_SECRET not in html, (
        "JWT signing secret leaked into the frontend HTML. The secret must "
        "live only on the backend."
    )
    assert PASSWORD not in html, (
        "Plain-text password leaked into the frontend HTML. Credentials must "
        "not be rendered into the static bundle."
    )
