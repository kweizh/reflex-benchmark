"""Final-state verification for the background_task_progress_bar Reflex task.

These tests are executed with the system python3 interpreter (NOT inside the
project's uv environment), so we cannot `import reflex` here. We rely on:

* static AST parsing of the user-written source file under ``myproject/myproject.py``;
* shelling out to ``uv`` (via ``subprocess``) to compile the Reflex frontend and
  start the dev server;
* searching the exported frontend bundle under ``.web/`` for the expected
  literals;
* HTTP smoke checks against the running app on ports 3000/8000.

All background servers spawned during verification are killed on teardown.
"""

import ast
import os
import re
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

PROJECT_DIR = "/home/user/myproject"
MAIN_FILE = os.path.join(PROJECT_DIR, "myproject", "myproject.py")
WEB_DIR = os.path.join(PROJECT_DIR, ".web")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source() -> str:
    assert os.path.isfile(MAIN_FILE), (
        f"Reflex main module not found at {MAIN_FILE}; the task must create the "
        f"`myproject` package."
    )
    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _parse_module() -> ast.Module:
    return ast.parse(_read_source())


def _iter_classdefs(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node


def _is_async_with_self(node: ast.AST) -> bool:
    """Return True if ``node`` is ``async with self:`` (one or more items, the
    first of which is ``self``)."""
    if not isinstance(node, ast.AsyncWith):
        return False
    for item in node.items:
        ctx = item.context_expr
        if isinstance(ctx, ast.Name) and ctx.id == "self":
            return True
    return False


def _is_rx_event_background_decorator(dec: ast.expr) -> bool:
    """Match ``@rx.event(background=True)`` (or ``@reflex.event(background=True)``)."""
    if not isinstance(dec, ast.Call):
        return False
    func = dec.func
    # Expecting an attribute access like rx.event
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr != "event":
        return False
    if not isinstance(func.value, ast.Name):
        return False
    if func.value.id not in ("rx", "reflex"):
        return False
    for kw in dec.keywords:
        if kw.arg == "background" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _find_state_class(tree: ast.Module) -> ast.ClassDef:
    """Return the first class subclassing ``rx.State`` (or ``State``)."""
    for cls in _iter_classdefs(tree):
        for base in cls.bases:
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                if base.value.id in ("rx", "reflex") and base.attr == "State":
                    return cls
            if isinstance(base, ast.Name) and base.id == "State":
                return cls
    raise AssertionError(
        "No State class (subclass of rx.State) found in myproject/myproject.py."
    )


def _annassign_info(node: ast.AnnAssign):
    """Extract (name, annotation_str, default_value_node)."""
    if not isinstance(node.target, ast.Name):
        return None
    name = node.target.id
    try:
        ann = ast.unparse(node.annotation)
    except Exception:
        ann = ""
    return name, ann.strip(), node.value


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _kill_bg_servers():
    for pattern in ("reflex run", "next-server", "next dev", "uvicorn", "reflex.app"):
        subprocess.run(["pkill", "-f", pattern], check=False)
    # Give the OS a moment to release the ports.
    time.sleep(1.0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def exported_frontend():
    """Compile the Reflex frontend so the exported assets exist under .web/.

    Uses ``uv run reflex export --frontend-only --no-zip`` from inside the
    project directory. Skips with a clear message if uv is unavailable.
    """
    if shutil.which("uv") is None:
        pytest.fail("uv is required to compile the Reflex frontend but was not found in PATH.")
    # Make sure no stale dev servers are holding ports.
    _kill_bg_servers()
    result = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed.\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert os.path.isdir(WEB_DIR), (
        f"Expected exported frontend at {WEB_DIR}, but it does not exist after `reflex export`."
    )
    yield WEB_DIR


@pytest.fixture(scope="module")
def running_app():
    """Start ``uv run reflex run`` in the background and wait for the
    frontend (3000) and backend (8000) ports to open.

    Teardown kills the server (and any orphans) so background servers are not
    left running.
    """
    if shutil.which("uv") is None:
        pytest.fail("uv is required to start the Reflex dev server but was not found in PATH.")
    _kill_bg_servers()
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 240
        ready_frontend = False
        ready_backend = False
        while time.time() < deadline:
            if not ready_frontend and _is_port_open("127.0.0.1", 3000):
                ready_frontend = True
            if not ready_backend and _is_port_open("127.0.0.1", 8000):
                ready_backend = True
            if ready_frontend and ready_backend:
                break
            if proc.poll() is not None:
                pytest.fail(
                    f"`uv run reflex run` exited prematurely with code {proc.returncode}."
                )
            time.sleep(2.0)
        assert ready_frontend, "Frontend did not start listening on port 3000 within timeout."
        assert ready_backend, "Backend did not start listening on port 8000 within timeout."
        yield
    finally:
        # Try graceful termination of the process group first.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        _kill_bg_servers()
        # Sanity-check ports are released.
        time.sleep(2.0)


# ---------------------------------------------------------------------------
# Static AST tests
# ---------------------------------------------------------------------------


def test_main_module_exists():
    assert os.path.isfile(MAIN_FILE), (
        f"Expected the Reflex app entry point at {MAIN_FILE}."
    )


def test_state_has_progress_var():
    tree = _parse_module()
    cls = _find_state_class(tree)
    found = False
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign):
            info = _annassign_info(stmt)
            if not info:
                continue
            name, ann, default = info
            if name == "progress" and ann == "int":
                assert isinstance(default, ast.Constant) and default.value == 0, (
                    f"`progress` must default to 0, found default {ast.dump(default) if default else None}."
                )
                found = True
                break
    assert found, "State class must define `progress: int = 0`."


def test_state_has_status_message_var():
    tree = _parse_module()
    cls = _find_state_class(tree)
    found = False
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign):
            info = _annassign_info(stmt)
            if not info:
                continue
            name, ann, default = info
            if name == "status_message" and ann == "str":
                assert isinstance(default, ast.Constant) and default.value == "Ready", (
                    f"`status_message` must default to \"Ready\", found {ast.dump(default) if default else None}."
                )
                found = True
                break
    assert found, "State class must define `status_message: str = \"Ready\"`."


def test_state_has_backend_only_running_flag():
    """Find a backend-only (underscore-prefixed) bool field defaulting to False."""
    tree = _parse_module()
    cls = _find_state_class(tree)
    found = False
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign):
            info = _annassign_info(stmt)
            if not info:
                continue
            name, ann, default = info
            if (
                name.startswith("_")
                and ann == "bool"
                and isinstance(default, ast.Constant)
                and default.value is False
            ):
                found = True
                break
    assert found, (
        "State class must define a backend-only boolean var (underscore-prefixed, "
        "e.g. `_task_running: bool = False`)."
    )


def test_background_event_handler_decorator_and_locks():
    """Check for @rx.event(background=True) and at least 3 `async with self:` blocks
    inside the decorated method."""
    tree = _parse_module()
    cls = _find_state_class(tree)
    bg_methods = []
    for stmt in cls.body:
        if isinstance(stmt, ast.AsyncFunctionDef):
            for dec in stmt.decorator_list:
                if _is_rx_event_background_decorator(dec):
                    bg_methods.append(stmt)
                    break
    assert bg_methods, (
        "No async method decorated with @rx.event(background=True) was found in the State class."
    )

    # Pick the first qualifying method and count `async with self:` blocks.
    method = bg_methods[0]
    async_with_self_count = sum(
        1 for node in ast.walk(method) if _is_async_with_self(node)
    )
    assert async_with_self_count >= 3, (
        f"Background event handler `{method.name}` must contain at least 3 "
        f"`async with self:` blocks, found {async_with_self_count}."
    )


def test_asyncio_sleep_outside_async_with_self():
    """`await asyncio.sleep(...)` must appear OUTSIDE every `async with self:`
    block within the background event handler."""
    tree = _parse_module()
    cls = _find_state_class(tree)

    bg_method = None
    for stmt in cls.body:
        if isinstance(stmt, ast.AsyncFunctionDef):
            for dec in stmt.decorator_list:
                if _is_rx_event_background_decorator(dec):
                    bg_method = stmt
                    break
            if bg_method:
                break
    assert bg_method is not None, (
        "Background event handler not found; cannot verify asyncio.sleep placement."
    )

    # Walk with a parent stack so we can determine whether each `asyncio.sleep`
    # call sits inside an `async with self:` block.
    found_outside = False

    def visit(node: ast.AST, in_async_with_self: bool):
        nonlocal found_outside
        if isinstance(node, ast.AsyncWith):
            entering_self = _is_async_with_self(node)
            new_state = in_async_with_self or entering_self
            for child in ast.iter_child_nodes(node):
                visit(child, new_state)
            return
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "sleep"
                and isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
            ):
                if not in_async_with_self:
                    found_outside = True
        for child in ast.iter_child_nodes(node):
            visit(child, in_async_with_self)

    visit(bg_method, False)
    assert found_outside, (
        "Expected at least one `asyncio.sleep(...)` call OUTSIDE every `async with self:` "
        "block inside the background event handler (to avoid blocking the UI)."
    )


# ---------------------------------------------------------------------------
# Frontend export tests
# ---------------------------------------------------------------------------


def _scan_frontend_for(pattern: re.Pattern, web_dir: str) -> bool:
    suffixes = (".js", ".jsx", ".ts", ".tsx", ".html", ".mjs")
    for root, dirs, files in os.walk(web_dir):
        # Skip heavy directories that don't carry compiled output we care about.
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".next/cache")]
        for fname in files:
            if not fname.endswith(suffixes):
                continue
            fpath = Path(root) / fname
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pattern.search(text):
                return True
    return False


def test_exported_frontend_contains_start_button(exported_frontend):
    """The compiled frontend must include the literal button label `Start`."""
    pattern = re.compile(r'"Start"|\'Start\'|>Start<')
    assert _scan_frontend_for(pattern, exported_frontend), (
        "Could not find the literal `Start` button label in the exported frontend under .web/."
    )


def test_exported_frontend_uses_progress_component(exported_frontend):
    """The compiled frontend must reference the Radix Progress component bound to the progress var."""
    progress_pattern = re.compile(
        r"RadixThemesProgress|radix[^\n]*Progress|from\s+['\"]@radix-ui/themes['\"][^\n]*Progress|<Progress\b",
        re.IGNORECASE,
    )
    assert _scan_frontend_for(progress_pattern, exported_frontend), (
        "Could not find a reference to the Radix Progress component in the exported frontend under .web/."
    )

    # And confirm the `progress` state var is used to drive a value somewhere.
    value_binding_pattern = re.compile(
        r"progress", re.IGNORECASE
    )
    assert _scan_frontend_for(value_binding_pattern, exported_frontend), (
        "Could not find any reference to the `progress` state var in the exported frontend."
    )


# ---------------------------------------------------------------------------
# Live application tests
# ---------------------------------------------------------------------------


def test_frontend_serves_root_with_start_label(running_app):
    import urllib.request

    req = urllib.request.Request("http://127.0.0.1:3000/", headers={"User-Agent": "harbor-verify"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200, f"Expected HTTP 200 from frontend, got {resp.status}."
        body = resp.read().decode("utf-8", errors="ignore")
    assert "Start" in body, (
        "Served HTML at http://localhost:3000/ does not contain the `Start` label."
    )


def test_backend_ping(running_app):
    import urllib.request

    req = urllib.request.Request("http://127.0.0.1:8000/ping")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status == 200, f"Backend /ping returned status {resp.status}."
    except Exception as exc:  # pragma: no cover - defensive
        pytest.fail(f"Reflex backend /ping endpoint not reachable: {exc!r}")


def test_no_lingering_servers_after_teardown(running_app):
    """Sentinel test that simply depends on the fixture so its teardown runs and
    kills any background servers spawned for verification."""
    # The actual teardown happens after this test completes via the fixture.
    assert True
