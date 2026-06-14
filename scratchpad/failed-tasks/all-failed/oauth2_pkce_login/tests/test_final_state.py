import base64
import hashlib
import json
import os
import re
import secrets
import socket
import time
from typing import Tuple
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/oauth_app"
CREDENTIALS_PATH = os.path.join(PROJECT_DIR, "credentials.json")
BACKEND_BASE = "http://localhost:8000"
PORT = 8000


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _wait_for_backend(timeout: float = 180.0) -> None:
    """Wait until the Reflex backend is accepting HTTP requests."""
    deadline = time.time() + timeout
    last_exc: Exception | None = None
    while time.time() < deadline:
        if _port_open("localhost", PORT):
            try:
                r = httpx.get(f"{BACKEND_BASE}/ping", timeout=5.0)
                if r.status_code < 500:
                    return
            except Exception as e:  # noqa: BLE001
                last_exc = e
        try:
            r = httpx.get(f"{BACKEND_BASE}/", timeout=5.0)
            if r.status_code < 500:
                return
        except Exception as e:  # noqa: BLE001
            last_exc = e
        time.sleep(2.0)
    raise RuntimeError(
        f"Backend at {BACKEND_BASE} did not become ready within {timeout}s; "
        f"last error: {last_exc!r}"
    )


@pytest.fixture(scope="session")
def reflex_server(xprocess):
    class Starter(ProcessStarter):
        name = "reflex_server"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 240
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open("localhost", PORT):
                return False
            try:
                r = httpx.get(f"{BACKEND_BASE}/ping", timeout=3.0)
                return r.status_code < 500
            except Exception:
                try:
                    r = httpx.get(f"{BACKEND_BASE}/", timeout=3.0)
                    return r.status_code < 500
                except Exception:
                    return False

    xprocess.ensure(Starter.name, Starter)
    _wait_for_backend()
    yield
    info = xprocess.getinfo(Starter.name)
    info.terminate()


@pytest.fixture(scope="session")
def credentials(reflex_server):
    assert os.path.isfile(CREDENTIALS_PATH), (
        f"Expected credentials file at {CREDENTIALS_PATH}; "
        "the project must write its generated client_id/client_secret/"
        "redirect_uri/username there."
    )
    with open(CREDENTIALS_PATH) as f:
        data = json.load(f)
    for key in ("client_id", "client_secret", "redirect_uri", "username"):
        assert key in data and isinstance(data[key], str) and data[key], (
            f"credentials.json missing or empty key: {key!r} (got {data!r})"
        )
    assert data["redirect_uri"] == f"{BACKEND_BASE}/auth/callback", (
        f"redirect_uri must be {BACKEND_BASE}/auth/callback; "
        f"got {data['redirect_uri']!r}"
    )
    return data


# --------------------------------------------------------------------------- #
# PKCE helpers
# --------------------------------------------------------------------------- #


def make_pkce() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _authorize_and_get_code(
    creds: dict, challenge: str, state: str, method: str = "S256"
) -> httpx.Response:
    params = {
        "client_id": creds["client_id"],
        "redirect_uri": creds["redirect_uri"],
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": method,
        "state": state,
    }
    return httpx.get(
        f"{BACKEND_BASE}/auth/authorize",
        params=params,
        follow_redirects=False,
        timeout=10.0,
    )


def _extract_code_and_state(location: str) -> Tuple[str, str]:
    parsed = urlparse(location)
    qs = parse_qs(parsed.query)
    code_vals = qs.get("code", [])
    state_vals = qs.get("state", [])
    assert code_vals, f"Authorize redirect missing `code` param: {location!r}"
    assert state_vals, f"Authorize redirect missing `state` param: {location!r}"
    return code_vals[0], state_vals[0]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_credentials_file_present_and_valid(credentials):
    """credentials.json was loaded successfully by the fixture."""
    assert credentials["client_id"], "client_id must be non-empty"
    assert credentials["client_secret"], "client_secret must be non-empty"


def test_authorize_happy_path_redirects_with_code(credentials):
    """`GET /auth/authorize` with valid PKCE params returns a 302 to the redirect_uri."""
    state = secrets.token_urlsafe(16)
    _verifier, challenge = make_pkce()
    resp = _authorize_and_get_code(credentials, challenge, state)
    assert resp.status_code == 302, (
        f"/auth/authorize happy path should return 302, got {resp.status_code} "
        f"body={resp.text[:200]!r}"
    )
    location = resp.headers.get("location") or resp.headers.get("Location")
    assert location, "/auth/authorize response missing Location header"
    parsed = urlparse(location)
    assert parsed.path == "/auth/callback", (
        f"Location should point to /auth/callback path; got {location!r}"
    )
    code, returned_state = _extract_code_and_state(location)
    assert returned_state == state, (
        f"Returned state {returned_state!r} does not match requested {state!r}"
    )
    assert code, "Authorize redirect must contain a non-empty `code` param"


def test_authorize_rejects_non_s256_challenge_method(credentials):
    """`code_challenge_method=plain` must be rejected with HTTP 400."""
    state = secrets.token_urlsafe(16)
    _verifier, challenge = make_pkce()
    resp = _authorize_and_get_code(credentials, challenge, state, method="plain")
    assert resp.status_code == 400, (
        f"/auth/authorize with method=plain should return 400, "
        f"got {resp.status_code}"
    )
    try:
        body = resp.json()
    except json.JSONDecodeError:
        pytest.fail(
            f"/auth/authorize 400 response should be JSON, got: {resp.text[:200]!r}"
        )
    assert isinstance(body, dict) and "error" in body, (
        f"/auth/authorize 400 response should contain an `error` JSON field; "
        f"got {body!r}"
    )


def test_token_rejects_wrong_verifier(credentials):
    """PKCE S256 enforcement: wrong code_verifier must yield invalid_grant."""
    state = secrets.token_urlsafe(16)
    _verifier, challenge = make_pkce()
    auth_resp = _authorize_and_get_code(credentials, challenge, state)
    assert auth_resp.status_code == 302, (
        f"Setup failure: /auth/authorize did not redirect: {auth_resp.status_code}"
    )
    location = auth_resp.headers.get("location") or auth_resp.headers["Location"]
    code, _ = _extract_code_and_state(location)

    wrong_verifier = secrets.token_urlsafe(64)
    resp = httpx.post(
        f"{BACKEND_BASE}/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": credentials["redirect_uri"],
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "code_verifier": wrong_verifier,
        },
        timeout=10.0,
    )
    assert resp.status_code == 400, (
        f"/auth/token with wrong verifier should return 400, got {resp.status_code} "
        f"body={resp.text[:200]!r}"
    )
    try:
        body = resp.json()
    except json.JSONDecodeError:
        pytest.fail(
            f"/auth/token 400 response should be JSON, got: {resp.text[:200]!r}"
        )
    err = body.get("error") if isinstance(body, dict) else None
    assert err == "invalid_grant", (
        f"Expected error=invalid_grant for failed PKCE S256, got {body!r}"
    )


def test_token_happy_path_returns_bearer_token(credentials):
    """A correct verifier returns access_token/token_type/expires_in."""
    state = secrets.token_urlsafe(16)
    verifier, challenge = make_pkce()
    auth_resp = _authorize_and_get_code(credentials, challenge, state)
    assert auth_resp.status_code == 302
    location = auth_resp.headers.get("location") or auth_resp.headers["Location"]
    code, _ = _extract_code_and_state(location)

    resp = httpx.post(
        f"{BACKEND_BASE}/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": credentials["redirect_uri"],
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "code_verifier": verifier,
        },
        timeout=10.0,
    )
    assert resp.status_code == 200, (
        f"/auth/token happy path expected 200, got {resp.status_code} "
        f"body={resp.text[:200]!r}"
    )
    body = resp.json()
    assert isinstance(body, dict), f"/auth/token body must be a JSON object: {body!r}"
    assert isinstance(body.get("access_token"), str) and body["access_token"], (
        f"access_token must be a non-empty string; got {body!r}"
    )
    assert body.get("token_type") == "Bearer", (
        f"token_type must be 'Bearer'; got {body.get('token_type')!r}"
    )
    assert isinstance(body.get("expires_in"), int), (
        f"expires_in must be an integer; got {body.get('expires_in')!r}"
    )


def test_api_me_requires_bearer_token(credentials):
    """`/api/me` returns 401 without bearer, 200 with a freshly issued bearer."""
    # No header -> 401
    resp = httpx.get(f"{BACKEND_BASE}/api/me", timeout=10.0)
    assert resp.status_code == 401, (
        f"/api/me without Authorization should be 401, got {resp.status_code}"
    )

    # Invalid token -> 401
    resp = httpx.get(
        f"{BACKEND_BASE}/api/me",
        headers={"Authorization": "Bearer not-a-real-token"},
        timeout=10.0,
    )
    assert resp.status_code == 401, (
        f"/api/me with bogus token should be 401, got {resp.status_code}"
    )

    # Valid token -> 200 + username
    state = secrets.token_urlsafe(16)
    verifier, challenge = make_pkce()
    auth_resp = _authorize_and_get_code(credentials, challenge, state)
    location = auth_resp.headers.get("location") or auth_resp.headers["Location"]
    code, _ = _extract_code_and_state(location)
    token_resp = httpx.post(
        f"{BACKEND_BASE}/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": credentials["redirect_uri"],
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "code_verifier": verifier,
        },
        timeout=10.0,
    )
    assert token_resp.status_code == 200, (
        f"Failed to mint token for /api/me test: {token_resp.status_code} "
        f"{token_resp.text[:200]!r}"
    )
    token = token_resp.json()["access_token"]

    resp = httpx.get(
        f"{BACKEND_BASE}/api/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert resp.status_code == 200, (
        f"/api/me with valid token should be 200, got {resp.status_code} "
        f"body={resp.text[:200]!r}"
    )
    body = resp.json()
    assert isinstance(body, dict), f"/api/me body must be a JSON object: {body!r}"
    username = body.get("username")
    assert isinstance(username, str) and username, (
        f"/api/me must return a non-empty `username` field; got {body!r}"
    )
    assert username == credentials["username"], (
        f"/api/me username mismatch: expected {credentials['username']!r}, "
        f"got {username!r}"
    )


def test_auth_start_redirects_to_authorize_with_s256(credentials):
    """`/auth/start` 302's to `/auth/authorize` with `code_challenge_method=S256`."""
    resp = httpx.get(
        f"{BACKEND_BASE}/auth/start", follow_redirects=False, timeout=10.0
    )
    assert resp.status_code == 302, (
        f"/auth/start should return 302, got {resp.status_code}"
    )
    location = resp.headers.get("location") or resp.headers.get("Location")
    assert location, "/auth/start response missing Location header"
    parsed = urlparse(location)
    # Accept either absolute URL or relative path.
    assert parsed.path == "/auth/authorize", (
        f"/auth/start should redirect to /auth/authorize; got {location!r}"
    )
    qs = parse_qs(parsed.query)
    assert qs.get("code_challenge_method") == ["S256"], (
        f"/auth/start must request S256; got {qs!r}"
    )
    assert qs.get("code_challenge") and qs["code_challenge"][0], (
        f"/auth/start must include a non-empty code_challenge; got {qs!r}"
    )
    assert qs.get("state") and qs["state"][0], (
        f"/auth/start must include a non-empty state; got {qs!r}"
    )


def test_full_flow_sets_access_token_cookie(credentials):
    """End-to-end: /auth/start -> /auth/authorize -> /auth/callback -> /,
    and the final cookie jar contains a non-HttpOnly `access_token` cookie."""
    with httpx.Client(
        follow_redirects=True, timeout=15.0, base_url=BACKEND_BASE
    ) as client:
        final = client.get("/auth/start")
        assert final.status_code == 200, (
            f"End-to-end flow final status expected 200, got {final.status_code} "
            f"url={final.url!s}"
        )
        # Final URL should be the home page.
        assert str(final.url).rstrip("/") == BACKEND_BASE.rstrip("/"), (
            f"End-to-end flow should land on the home page; final URL = {final.url!s}"
        )
        # The cookie jar must contain `access_token`.
        access_cookie = client.cookies.get("access_token")
        assert access_cookie, (
            f"After the full flow, the client cookie jar must contain a non-empty "
            f"`access_token` cookie; got cookies={dict(client.cookies)!r}"
        )

        # Inspect the redirect history for the /auth/callback hop and verify
        # its Set-Cookie header does NOT include HttpOnly.
        callback_resp = None
        for hist in final.history:
            if "/auth/callback" in str(hist.url):
                callback_resp = hist
                break
        assert callback_resp is not None, (
            f"End-to-end flow did not pass through /auth/callback; "
            f"history urls = {[str(h.url) for h in final.history]!r}"
        )
        assert callback_resp.status_code == 302, (
            f"/auth/callback should respond 302; got {callback_resp.status_code}"
        )
        set_cookie = callback_resp.headers.get_list("set-cookie")
        joined = " || ".join(set_cookie)
        assert "access_token" in joined.lower() or "access_token=" in joined, (
            f"/auth/callback must set the access_token cookie via Set-Cookie; "
            f"got {set_cookie!r}"
        )
        # access_token cookie must NOT be HttpOnly.
        cookie_lines = [
            line for line in set_cookie if line.lower().startswith("access_token=")
        ]
        assert cookie_lines, (
            f"No `access_token=...` Set-Cookie line found in /auth/callback "
            f"response; got {set_cookie!r}"
        )
        for line in cookie_lines:
            assert "httponly" not in line.lower(), (
                f"access_token cookie must NOT be HttpOnly; got {line!r}"
            )


def test_reflex_backend_is_alive(credentials):
    """Sanity: the Reflex `_event` endpoint exists (Reflex backend is running)."""
    # Reflex backend exposes /ping returning 'pong'.
    r = httpx.get(f"{BACKEND_BASE}/ping", timeout=5.0)
    assert r.status_code < 500, (
        f"/ping must respond < 500 when the Reflex backend is running; "
        f"got {r.status_code}"
    )


def test_state_design_has_cookie_and_backend_only_var(reflex_server):
    """Source-level inspection: the state module must declare both an rx.Cookie
    `access_token` field AND a backend-only var that mirrors the token."""
    py_files = []
    for root, _dirs, files in os.walk(PROJECT_DIR):
        # Skip virtualenvs, build artifacts, and node_modules.
        skip_substrings = (".venv", "node_modules", ".web", "__pycache__")
        if any(s in root for s in skip_substrings):
            continue
        for fname in files:
            if fname.endswith(".py"):
                py_files.append(os.path.join(root, fname))
    assert py_files, f"No Python source files found under {PROJECT_DIR}"

    cookie_pat = re.compile(
        r"access_token\s*(?::\s*[^=]+)?=\s*rx\.Cookie\s*\(", re.MULTILINE
    )
    backend_var_pat = re.compile(
        r"^\s*(_[A-Za-z0-9_]*(?:access_)?token[A-Za-z0-9_]*)\s*(?::\s*[^=]+)?=",
        re.MULTILINE,
    )
    mirror_pat = re.compile(
        r"self\._[A-Za-z0-9_]*token[A-Za-z0-9_]*\s*=\s*self\.access_token",
        re.MULTILINE,
    )

    cookie_hits: list[str] = []
    backend_hits: list[str] = []
    mirror_hits: list[str] = []
    for path in py_files:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        if cookie_pat.search(text):
            cookie_hits.append(path)
        if backend_var_pat.search(text):
            backend_hits.append(path)
        if mirror_pat.search(text):
            mirror_hits.append(path)

    assert cookie_hits, (
        "Expected at least one Python file to declare `access_token = rx.Cookie(...)` "
        f"(searched {len(py_files)} files under {PROJECT_DIR})"
    )
    assert backend_hits, (
        "Expected at least one Python file to declare a backend-only state var "
        "whose name starts with `_` and contains `token` (e.g. `_access_token: str = ...`); "
        f"searched {len(py_files)} files."
    )
    assert mirror_hits, (
        "Expected at least one Python file to mirror the cookie into the backend-only var "
        "(e.g. `self._access_token = self.access_token`); "
        f"searched {len(py_files)} files."
    )
