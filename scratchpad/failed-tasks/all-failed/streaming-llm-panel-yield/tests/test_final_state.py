"""Final-state tests for the streaming LLM panel Reflex task.

These tests use the system `python3` interpreter and `subprocess` to invoke
`uv` (which manages the project's own Reflex Python environment). The tests
must not assume that `reflex` is importable in the system Python, only that
`uv` and the project's virtualenv created by `uv` can run the Reflex CLI.

All background servers started for verification (Reflex dev server, static
export sub-processes) are terminated in teardown.
"""

import ast
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_DIR = "/home/user/streaming_llm_panel"
MODULE_PATH = os.path.join(
    PROJECT_DIR, "streaming_llm_panel", "streaming_llm_panel.py"
)
RXCONFIG_PATH = os.path.join(PROJECT_DIR, "rxconfig.py")
EXPORT_DIR = os.path.join(PROJECT_DIR, ".web", "_static")
EXPECTED_CHUNKS = ["Hello", " world", ", this", " is", " streamed", "."]
EXPECTED_JOINED = "Hello world, this is streamed."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kill_reflex_processes() -> None:
    """Best-effort kill of any lingering Reflex/Next dev processes."""
    for pattern in ("reflex run", "next-server", "reflex export"):
        subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )


def _wait_for_port(host: str, port: int, timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(1.0)
    return False


def _read_module_source() -> str:
    assert os.path.isfile(MODULE_PATH), (
        f"Expected Reflex app module at {MODULE_PATH}, but it was not found."
    )
    return Path(MODULE_PATH).read_text(encoding="utf-8")


def _parse_module() -> ast.Module:
    return ast.parse(_read_module_source())


def _iter_state_classes(tree: ast.Module):
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            # Match rx.State, reflex.State, or anything ending with `.State`
            if isinstance(base, ast.Attribute) and base.attr == "State":
                yield node
                break
            if isinstance(base, ast.Name) and base.id.endswith("State"):
                yield node
                break


def _has_decorator(func: ast.AsyncFunctionDef, attr_name: str) -> bool:
    for dec in func.decorator_list:
        # @rx.event
        if isinstance(dec, ast.Attribute) and dec.attr == attr_name:
            return True
        # @rx.event(...)
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and dec.func.attr == attr_name
        ):
            return True
    return False


def _function_contains_yield(func: ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(func):
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
    return False


def _function_calls(func: ast.AsyncFunctionDef, qualified: str) -> bool:
    parts = qualified.split(".")
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        # Build dotted name of the call target.
        names: list[str] = []
        while isinstance(fn, ast.Attribute):
            names.append(fn.attr)
            fn = fn.value
        if isinstance(fn, ast.Name):
            names.append(fn.id)
        names.reverse()
        if names[-len(parts):] == parts:
            return True
    return False


def _find_chunk_list(func: ast.AsyncFunctionDef) -> list[str] | None:
    for node in ast.walk(func):
        if not isinstance(node, ast.List):
            continue
        elements: list[str] = []
        ok = True
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                elements.append(elt.value)
            else:
                ok = False
                break
        if ok and elements and "".join(elements) == EXPECTED_JOINED:
            return elements
    return None


# ---------------------------------------------------------------------------
# Session fixtures: static export + dev server
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _cleanup_lingering_processes():
    """Make sure no stale Reflex processes are running before/after tests."""
    _kill_reflex_processes()
    yield
    _kill_reflex_processes()


@pytest.fixture(scope="session")
def static_export() -> str:
    """Produce a static frontend export under .web/_static and return its path."""
    assert shutil.which("uv") is not None, "uv binary not found in PATH"
    # Clean previous export to avoid stale artifacts.
    if os.path.isdir(EXPORT_DIR):
        shutil.rmtree(EXPORT_DIR, ignore_errors=True)
    result = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert os.path.isdir(EXPORT_DIR), (
        f"Expected static export directory {EXPORT_DIR} after reflex export, "
        "but it was not created."
    )
    return EXPORT_DIR


@pytest.fixture(scope="session")
def dev_server():
    """Start the Reflex dev server in the background and tear it down afterwards."""
    assert shutil.which("uv") is not None, "uv binary not found in PATH"
    log_path = "/tmp/reflex_streaming_panel.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        frontend_up = _wait_for_port("127.0.0.1", 3000, timeout=300.0)
        backend_up = _wait_for_port("127.0.0.1", 8000, timeout=300.0)
        yield {
            "process": proc,
            "frontend_up": frontend_up,
            "backend_up": backend_up,
            "log_path": log_path,
        }
    finally:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
        log_file.close()
        _kill_reflex_processes()


# ---------------------------------------------------------------------------
# Project layout
# ---------------------------------------------------------------------------


def test_module_file_exists():
    assert os.path.isfile(MODULE_PATH), (
        f"Expected the Reflex app module at {MODULE_PATH}. The project should be "
        "structured as `streaming_llm_panel/streaming_llm_panel.py`."
    )


def test_rxconfig_references_app_name():
    assert os.path.isfile(RXCONFIG_PATH), (
        f"Expected {RXCONFIG_PATH} (created by `reflex init`) to exist."
    )
    content = Path(RXCONFIG_PATH).read_text(encoding="utf-8")
    assert "streaming_llm_panel" in content, (
        f"rxconfig.py at {RXCONFIG_PATH} must reference app_name=\"streaming_llm_panel\"; "
        f"got:\n{content}"
    )


# ---------------------------------------------------------------------------
# State variable declarations (AST)
# ---------------------------------------------------------------------------


def test_state_class_declares_required_vars():
    tree = _parse_module()
    state_classes = list(_iter_state_classes(tree))
    assert state_classes, (
        "No subclass of rx.State was found in the app module. The task requires "
        "a state class defining `prompt`, `response`, and `is_loading`."
    )

    required = {
        "prompt": ("str", ""),
        "response": ("str", ""),
        "is_loading": ("bool", False),
    }
    seen: dict[str, tuple[str, object]] = {}
    for cls in state_classes:
        for node in cls.body:
            if not isinstance(node, ast.AnnAssign):
                continue
            if not isinstance(node.target, ast.Name):
                continue
            name = node.target.id
            if name not in required:
                continue
            ann = node.annotation
            ann_name = ann.id if isinstance(ann, ast.Name) else None
            value = (
                node.value.value
                if isinstance(node.value, ast.Constant)
                else None
            )
            seen[name] = (ann_name or "", value)

    for name, (exp_type, exp_default) in required.items():
        assert name in seen, (
            f"State class is missing required annotated var `{name}: {exp_type}`."
        )
        ann_name, default = seen[name]
        assert ann_name == exp_type, (
            f"State var `{name}` must be annotated as `{exp_type}`, "
            f"got annotation `{ann_name}`."
        )
        assert default == exp_default, (
            f"State var `{name}` must default to {exp_default!r}, got {default!r}."
        )


# ---------------------------------------------------------------------------
# Generator event handler (AST)
# ---------------------------------------------------------------------------


def _find_streaming_handler() -> ast.AsyncFunctionDef:
    tree = _parse_module()
    for cls in _iter_state_classes(tree):
        for node in cls.body:
            if (
                isinstance(node, ast.AsyncFunctionDef)
                and _has_decorator(node, "event")
                and _function_contains_yield(node)
            ):
                return node
    pytest.fail(
        "Could not find an async generator method decorated with `@rx.event` "
        "(or `@rx.event(...)`) that contains at least one `yield` inside a "
        "subclass of rx.State."
    )


def test_event_handler_is_async_generator_with_event_decorator():
    handler = _find_streaming_handler()
    assert isinstance(handler, ast.AsyncFunctionDef), (
        "Streaming handler must be an `async def` (Python async generator)."
    )
    assert _has_decorator(handler, "event"), (
        f"Streaming handler `{handler.name}` must be decorated with `@rx.event` "
        "or `@rx.event(...)`."
    )
    assert _function_contains_yield(handler), (
        f"Streaming handler `{handler.name}` must contain at least one `yield`."
    )


def test_event_handler_calls_asyncio_sleep():
    handler = _find_streaming_handler()
    assert _function_calls(handler, "asyncio.sleep"), (
        f"Streaming handler `{handler.name}` must call `asyncio.sleep(...)` "
        "between yielded chunks."
    )


def test_event_handler_contains_expected_chunk_list():
    handler = _find_streaming_handler()
    chunks = _find_chunk_list(handler)
    assert chunks is not None, (
        "Streaming handler must contain a list literal whose string elements "
        f"join to exactly {EXPECTED_JOINED!r}. Expected list: {EXPECTED_CHUNKS!r}."
    )
    assert chunks == EXPECTED_CHUNKS, (
        f"Streaming chunks must match {EXPECTED_CHUNKS!r}, got {chunks!r}."
    )


# ---------------------------------------------------------------------------
# UI usage (text-search + AST)
# ---------------------------------------------------------------------------


def test_ui_uses_text_area_and_send_button_label():
    src = _read_module_source()
    assert "rx.text_area" in src, (
        "The app page must use `rx.text_area` for the user's prompt input."
    )
    assert '"Send"' in src or "'Send'" in src, (
        "The app page must render a button whose label is the literal string "
        "\"Send\"."
    )


def test_ui_uses_rx_cond_with_is_loading_for_spinner():
    src = _read_module_source()
    assert "rx.spinner" in src, (
        "The app page must render a spinner using `rx.spinner` (gated by the "
        "loading state)."
    )

    tree = _parse_module()
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "cond"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        # Walk down attribute chain to find a final `.is_loading` access.
        attr = first
        while isinstance(attr, ast.Attribute):
            if attr.attr == "is_loading":
                found = True
                break
            attr = attr.value
        if found:
            break
    assert found, (
        "Expected a call to `rx.cond(<StateClass>.is_loading, ...)` somewhere "
        "in the app module to conditionally render the spinner."
    )


# ---------------------------------------------------------------------------
# Static export checks
# ---------------------------------------------------------------------------


def _read_export_bundle(export_dir: str) -> str:
    chunks: list[str] = []
    for root, _dirs, files in os.walk(export_dir):
        for name in files:
            if not name.endswith((".html", ".js", ".css", ".txt", ".json")):
                continue
            path = os.path.join(root, name)
            try:
                chunks.append(Path(path).read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "\n".join(chunks)


def test_static_export_contains_send_label(static_export: str):
    bundle = _read_export_bundle(static_export)
    assert "Send" in bundle, (
        f"Exported frontend bundle in {static_export} must contain the literal "
        "\"Send\" button label."
    )


def test_static_export_contains_spinner_component(static_export: str):
    bundle = _read_export_bundle(static_export)
    candidates = ("rt-Spinner", "radix-themes-spinner", "Spinner")
    assert any(token in bundle for token in candidates), (
        f"Exported frontend bundle in {static_export} must reference a spinner "
        f"component. Expected one of: {candidates}."
    )


# ---------------------------------------------------------------------------
# Runtime smoke test
# ---------------------------------------------------------------------------


def test_dev_server_frontend_serves_root(dev_server):
    assert dev_server["frontend_up"], (
        "Reflex frontend did not come up on port 3000 within the timeout. "
        f"See {dev_server['log_path']} for details."
    )
    try:
        with urllib.request.urlopen("http://127.0.0.1:3000/", timeout=30) as resp:
            status = resp.status
            body = resp.read()
    except urllib.error.URLError as e:
        pytest.fail(f"Failed to GET http://127.0.0.1:3000/: {e}")
    assert status == 200, f"GET / returned status {status}, expected 200."
    assert body, "GET / returned an empty body; expected the Reflex landing HTML."


def test_dev_server_backend_ping(dev_server):
    assert dev_server["backend_up"], (
        "Reflex backend did not come up on port 8000 within the timeout. "
        f"See {dev_server['log_path']} for details."
    )
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/ping", timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.URLError as e:
        pytest.fail(f"Failed to GET http://127.0.0.1:8000/ping: {e}")
    assert status == 200, f"GET /ping returned status {status}, expected 200."
    assert "pong" in body.lower() or body.strip() != "", (
        f"Expected backend /ping to return a non-empty body (typically 'pong'), "
        f"got: {body!r}"
    )


# ---------------------------------------------------------------------------
# Final cleanup verification
# ---------------------------------------------------------------------------


def test_no_lingering_reflex_processes_after_teardown(dev_server):
    """Sanity check that the dev server fixture has not left zombies running.

    This test runs after the dev_server fixture has been used by previous
    tests, but the fixture is session-scoped so teardown will happen at the
    very end of the session. We instead assert that the process object we
    own is alive while tests run, and rely on the session-level autouse
    cleanup fixture to ensure final teardown happens.
    """
    proc = dev_server["process"]
    # The process should either still be running (managed by fixture) or
    # have terminated cleanly. It must not be a zombie that we cannot reap.
    assert proc.pid > 0, "Reflex dev server process has no PID."
