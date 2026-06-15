import ast
import os
import re
import subprocess
import time
from pathlib import Path

import pytest
import requests


PROJECT_DIR = "/home/user/myapp"
APP_PKG_DIR = "/home/user/myapp/myapp"
BACKEND = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_py_files():
    base = Path(APP_PKG_DIR)
    if not base.is_dir():
        # Fallback: scan the whole project dir excluding venv / node_modules.
        base = Path(PROJECT_DIR)
    for p in base.rglob("*.py"):
        parts = set(p.parts)
        if any(skip in parts for skip in (".venv", "venv", "node_modules", ".web", "__pycache__")):
            continue
        yield p


def _load_modules():
    mods = []
    for p in _iter_py_files():
        try:
            src = p.read_text()
            tree = ast.parse(src)
            mods.append((p, src, tree))
        except (OSError, SyntaxError):
            continue
    return mods


def _is_attr(node, owner, attr):
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
        and node.attr == attr
    )


def _is_call_to(node, owner, attr):
    return isinstance(node, ast.Call) and _is_attr(node.func, owner, attr)


def _find_rx_app_call():
    """Find the rx.App(...) call and return (call_node, source, module_tree)."""
    for p, src, tree in _load_modules():
        for node in ast.walk(tree):
            if _is_call_to(node, "rx", "App"):
                return node, src, tree, p
    return None


def _find_fastapi_binding_name(tree):
    """Return a set of variable names bound to a FastAPI(...) instance."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.Call):
                func = value.func
                # FastAPI(...) or fastapi.FastAPI(...)
                if (isinstance(func, ast.Name) and func.id == "FastAPI") or (
                    isinstance(func, ast.Attribute) and func.attr == "FastAPI"
                ):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            names.add(t.id)
    return names


# ---------------------------------------------------------------------------
# AST tests
# ---------------------------------------------------------------------------


def test_rx_app_uses_api_transformer_with_fastapi_instance():
    """rx.App(... api_transformer=<fastapi_instance>) must exist."""
    result = _find_rx_app_call()
    assert result is not None, (
        "Could not find any rx.App(...) call in the project sources."
    )
    call, _src, tree, _path = result
    api_kw = None
    for kw in call.keywords:
        if kw.arg == "api_transformer":
            api_kw = kw
            break
    assert api_kw is not None, (
        "rx.App(...) does not receive an 'api_transformer' keyword argument."
    )

    # Resolve the FastAPI instance: either an inline FastAPI(...) call or a Name
    # bound to a FastAPI(...) instance.
    value = api_kw.value
    if isinstance(value, ast.Call):
        func = value.func
        ok = (isinstance(func, ast.Name) and func.id == "FastAPI") or (
            isinstance(func, ast.Attribute) and func.attr == "FastAPI"
        )
        assert ok, "api_transformer is a Call but not to FastAPI(...)."
        return

    assert isinstance(value, ast.Name), (
        "api_transformer must reference a FastAPI instance (name or inline call)."
    )
    fastapi_names = _find_fastapi_binding_name(tree)
    assert value.id in fastapi_names, (
        f"api_transformer references '{value.id}' which is not bound to a FastAPI() instance."
    )


def _decorator_call_targets(tree):
    """Yield tuples (attr_name, method, route_literal) for any @<name>.<method>('<route>') decorators."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if (
                    isinstance(deco, ast.Call)
                    and isinstance(deco.func, ast.Attribute)
                    and isinstance(deco.func.value, ast.Name)
                ):
                    method = deco.func.attr
                    name = deco.func.value.id
                    route = None
                    if deco.args and isinstance(deco.args[0], ast.Constant) and isinstance(deco.args[0].value, str):
                        route = deco.args[0].value
                    if route is not None:
                        yield name, method, route


def test_endpoints_registered_on_fastapi_instance():
    """`@<fastapi_app>.post('/api/login')` and `@<fastapi_app>.get('/api/me')` must exist on the same FastAPI instance referenced by api_transformer."""
    result = _find_rx_app_call()
    assert result is not None, "Missing rx.App(...) call."
    call, _src, tree, _path = result

    # Identify which FastAPI binding feeds api_transformer.
    api_kw = next((kw for kw in call.keywords if kw.arg == "api_transformer"), None)
    assert api_kw is not None
    target_name = None
    if isinstance(api_kw.value, ast.Name):
        target_name = api_kw.value.id

    found_login = False
    found_me = False
    for name, method, route in _decorator_call_targets(tree):
        if target_name is not None and name != target_name:
            continue
        if method == "post" and route == "/api/login":
            found_login = True
        if method == "get" and route == "/api/me":
            found_me = True

    assert found_login, (
        "Expected a `@<fastapi_app>.post('/api/login')` decorator on the FastAPI instance "
        "passed to rx.App(api_transformer=...)."
    )
    assert found_me, (
        "Expected a `@<fastapi_app>.get('/api/me')` decorator on the FastAPI instance "
        "passed to rx.App(api_transformer=...)."
    )


def test_jwt_secret_generated_with_secure_random():
    """JWT signing secret must come from secrets.token_urlsafe / secrets.token_hex / os.urandom."""
    found_secure_random = False
    forbidden_env_access = []

    for _p, src, tree in _load_modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # secrets.token_urlsafe / secrets.token_hex / os.urandom
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id == "secrets" and func.attr in {"token_urlsafe", "token_hex"}:
                        found_secure_random = True
                    if func.value.id == "os" and func.attr == "urandom":
                        found_secure_random = True

        # Look for any environ access whose key references a JWT / secret-style name.
        # We do a regex scan to keep it robust against `os.environ.get`, `os.getenv`,
        # and direct subscription.
        for m in re.finditer(
            r"""(?:os\.environ\.get|os\.getenv|os\.environ\[)\s*\(?\s*['\"]([^'\"]+)['\"]""",
            src,
        ):
            key = m.group(1).upper()
            if "JWT" in key or "SECRET" in key:
                forbidden_env_access.append(key)

    assert found_secure_random, (
        "JWT secret was not generated using secrets.token_urlsafe, secrets.token_hex, or os.urandom."
    )
    assert not forbidden_env_access, (
        f"JWT/SECRET values must NOT be read from environment variables. Found: {forbidden_env_access}"
    )


def test_state_has_backend_only_current_user():
    """A class (an rx.State subclass) must declare a backend-only var '_current_user'."""
    state_class_found = False
    current_user_in_state = False

    for _p, _src, tree in _load_modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # Heuristically detect rx.State subclasses (rx.State, or a name containing 'State').
            is_state_like = False
            for base in node.bases:
                if isinstance(base, ast.Attribute) and base.attr == "State":
                    is_state_like = True
                if isinstance(base, ast.Name) and base.id.endswith("State"):
                    is_state_like = True
            # Check body for _current_user declaration
            has_curr = False
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    if stmt.target.id == "_current_user":
                        has_curr = True
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name) and t.id == "_current_user":
                            has_curr = True
            if is_state_like:
                state_class_found = True
                if has_curr:
                    current_user_in_state = True

    assert state_class_found, "No rx.State subclass (or *State subclass) found in the project."
    assert current_user_in_state, (
        "A rx.State subclass must declare a backend-only var named '_current_user' (leading underscore)."
    )


# ---------------------------------------------------------------------------
# Runtime tests
# ---------------------------------------------------------------------------


def _port_open(host: str, port: int) -> bool:
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _kill_servers():
    for pattern in ("reflex run", "uvicorn", "granian"):
        subprocess.run(["pkill", "-f", pattern], check=False)


@pytest.fixture(scope="module")
def reflex_backend():
    _kill_servers()
    # Give the OS a moment to free the ports.
    time.sleep(2)

    env = os.environ.copy()
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--backend-only", "--loglevel", "debug"],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    started = False
    deadline = time.time() + 240
    last_err = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            r = requests.get(f"{BACKEND}/ping", timeout=2)
            if r.status_code == 200 and "pong" in r.text.lower():
                started = True
                break
        except Exception as e:
            last_err = str(e)
        time.sleep(2)

    if not started:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        _kill_servers()
        pytest.fail(
            f"Reflex backend did not become ready on {BACKEND}/ping within timeout. "
            f"Last error: {last_err}"
        )

    yield

    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    _kill_servers()
    time.sleep(2)


def test_login_with_correct_credentials_returns_access_token(reflex_backend):
    r = requests.post(
        f"{BACKEND}/api/login",
        json={"username": "admin", "password": "secret"},
        timeout=10,
    )
    assert r.status_code == 200, (
        f"Expected 200 OK from POST /api/login with valid credentials, got {r.status_code}: {r.text}"
    )
    body = r.json()
    assert isinstance(body, dict), f"Login response is not a JSON object: {body!r}"
    assert "access_token" in body, f"Login response missing 'access_token': {body!r}"
    assert isinstance(body["access_token"], str) and body["access_token"], (
        "access_token must be a non-empty string."
    )


def test_login_with_wrong_credentials_returns_401(reflex_backend):
    r = requests.post(
        f"{BACKEND}/api/login",
        json={"username": "admin", "password": "wrong"},
        timeout=10,
    )
    assert r.status_code == 401, (
        f"Expected 401 from POST /api/login with invalid credentials, got {r.status_code}: {r.text}"
    )


def test_me_with_valid_token_returns_admin(reflex_backend):
    login = requests.post(
        f"{BACKEND}/api/login",
        json={"username": "admin", "password": "secret"},
        timeout=10,
    )
    assert login.status_code == 200, f"Login failed: {login.status_code} {login.text}"
    token = login.json().get("access_token")
    assert token, "Login response did not include access_token."

    r = requests.get(
        f"{BACKEND}/api/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert r.status_code == 200, (
        f"Expected 200 OK from GET /api/me with valid token, got {r.status_code}: {r.text}"
    )
    assert r.json() == {"user": "admin"}, (
        f"Expected GET /api/me to return {{'user': 'admin'}}, got: {r.text}"
    )


def test_me_without_token_returns_unauthorized(reflex_backend):
    r = requests.get(f"{BACKEND}/api/me", timeout=10)
    assert r.status_code in (401, 403), (
        f"Expected 401 or 403 from GET /api/me without a token, got {r.status_code}: {r.text}"
    )


def test_me_with_malformed_token_returns_unauthorized(reflex_backend):
    r = requests.get(
        f"{BACKEND}/api/me",
        headers={"Authorization": "Bearer not.a.real.token"},
        timeout=10,
    )
    assert r.status_code in (401, 403), (
        f"Expected 401 or 403 from GET /api/me with malformed token, got {r.status_code}: {r.text}"
    )
