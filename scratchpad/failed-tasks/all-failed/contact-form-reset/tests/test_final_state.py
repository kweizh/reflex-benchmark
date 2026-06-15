"""Final-state verification for the Reflex contact-form-reset task.

These tests run with the system `python3` (no Reflex installed at the verifier
level). They use only the standard library plus `pytest`.

Two layers of verification:

1. AST scan of the project's Python source files to confirm the State
   contract (vars, defaults, cached computed var, on_submit handler).
2. HTTP scan of the running Reflex dev server to confirm the rendered
   form contains the three named inputs and a Submit button.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import signal
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Iterable

import pytest

PROJECT_DIR = "/home/user/myproject"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}/"

EXCLUDE_DIR_NAMES = {
    ".venv",
    "venv",
    ".web",
    ".reflex",
    "__pycache__",
    "node_modules",
    ".git",
    "assets",
    "dist",
    "build",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_project_py_files(root: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place so os.walk does not descend.
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _parse_modules(root: str) -> list[tuple[str, ast.Module]]:
    parsed: list[tuple[str, ast.Module]] = []
    for path in _iter_project_py_files(root):
        try:
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            parsed.append((path, ast.parse(src)))
        except (SyntaxError, UnicodeDecodeError):
            # Skip unparseable files (could be auto-generated artifacts).
            continue
    return parsed


def _attr_chain(node: ast.AST) -> list[str]:
    """Return dotted-attribute chain for `a.b.c`-style nodes (left to right)."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    parts.reverse()
    return parts


def _is_rx_state_base(base: ast.expr) -> bool:
    chain = _attr_chain(base)
    if not chain:
        return False
    # Accept `rx.State`, `reflex.State`, and bare `State` (uncommon but tolerated).
    if chain[-1] != "State":
        return False
    if len(chain) == 1:
        return True  # bare `State` - tolerate
    return chain[0] in {"rx", "reflex"}


def _find_state_classes(modules: list[tuple[str, ast.Module]]) -> list[tuple[str, ast.ClassDef]]:
    found: list[tuple[str, ast.ClassDef]] = []
    for path, mod in modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if _is_rx_state_base(base):
                        found.append((path, node))
                        break
    return found


def _annotation_matches_list_dict(ann: ast.expr) -> bool:
    """True if annotation is list[dict] / List[dict] / list[Dict[...]], etc."""
    if not isinstance(ann, ast.Subscript):
        return False
    outer = _attr_chain(ann.value)
    if not outer or outer[-1] not in {"list", "List"}:
        return False
    inner = ann.slice
    if isinstance(inner, ast.Tuple):  # unusual; not our case
        return False
    inner_chain = _attr_chain(inner) if not isinstance(inner, ast.Subscript) else _attr_chain(inner.value)
    if not inner_chain:
        return False
    return inner_chain[-1] in {"dict", "Dict"}


def _annotation_matches_dict(ann: ast.expr) -> bool:
    """True if annotation is dict / dict[...] / Dict / Dict[...]."""
    if isinstance(ann, ast.Subscript):
        chain = _attr_chain(ann.value)
    else:
        chain = _attr_chain(ann)
    return bool(chain) and chain[-1] in {"dict", "Dict"}


def _is_empty_list(node: ast.expr) -> bool:
    return isinstance(node, ast.List) and not node.elts


def _is_empty_dict(node: ast.expr) -> bool:
    return isinstance(node, ast.Dict) and not node.keys


def _decorator_is_rx_var(dec: ast.expr) -> bool:
    """Match `@rx.var`, `@rx.var(...)`, `@reflex.var`, `@reflex.var(...)`."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    chain = _attr_chain(target)
    if not chain:
        return False
    return chain[-1] == "var" and chain[0] in {"rx", "reflex"}


def _returns_len_self_submissions(fn: ast.FunctionDef) -> bool:
    """True if function body returns `len(self.submissions)`."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "len"
                and len(call.args) == 1
                and isinstance(call.args[0], ast.Attribute)
                and call.args[0].attr == "submissions"
                and isinstance(call.args[0].value, ast.Name)
                and call.args[0].value.id == "self"
            ):
                return True
    return False


def _find_rx_form_calls_with_on_submit(modules: list[tuple[str, ast.Module]]) -> list[ast.Call]:
    matches: list[ast.Call] = []
    for _path, mod in modules:
        for node in ast.walk(mod):
            if not isinstance(node, ast.Call):
                continue
            chain = _attr_chain(node.func)
            if not chain:
                continue
            # Accept `rx.form`, `rx.form.root`, `reflex.form`, `reflex.form.root`.
            head = chain[0]
            if head not in {"rx", "reflex"}:
                continue
            tail = chain[1:]
            if tail not in (["form"], ["form", "root"]):
                continue
            for kw in node.keywords:
                if kw.arg == "on_submit":
                    matches.append(node)
                    break
    return matches


# ---------------------------------------------------------------------------
# AST scan tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def parsed_modules() -> list[tuple[str, ast.Module]]:
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."
    mods = _parse_modules(PROJECT_DIR)
    assert mods, f"No parseable Python source files found under {PROJECT_DIR}."
    return mods


@pytest.fixture(scope="session")
def state_classes(parsed_modules: list[tuple[str, ast.Module]]) -> list[tuple[str, ast.ClassDef]]:
    classes = _find_state_classes(parsed_modules)
    assert classes, (
        "No subclass of `rx.State` (or `reflex.State`) was found in the project. "
        "Define a State class that holds the form data."
    )
    return classes


def test_state_has_submissions_list_dict(state_classes):
    for _path, cls in state_classes:
        for stmt in cls.body:
            if (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == "submissions"
                and _annotation_matches_list_dict(stmt.annotation)
                and stmt.value is not None
                and _is_empty_list(stmt.value)
            ):
                return
    pytest.fail(
        "Expected a state var `submissions: list[dict] = []` on the rx.State "
        "subclass. None of the discovered State classes declare it with that "
        "exact annotation and default."
    )


def test_state_has_last_submission_dict(state_classes):
    for _path, cls in state_classes:
        for stmt in cls.body:
            if (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == "last_submission"
                and _annotation_matches_dict(stmt.annotation)
                and stmt.value is not None
                and _is_empty_dict(stmt.value)
            ):
                return
    pytest.fail(
        "Expected a state var `last_submission: dict = {}` (or `Dict[...]`) on "
        "the rx.State subclass with an empty-dict default. Not found."
    )


def test_state_has_cached_submission_count(state_classes):
    for _path, cls in state_classes:
        for stmt in cls.body:
            if not isinstance(stmt, ast.FunctionDef):
                continue
            if stmt.name != "submission_count":
                continue
            if not any(_decorator_is_rx_var(d) for d in stmt.decorator_list):
                continue
            if _returns_len_self_submissions(stmt):
                return
    pytest.fail(
        "Expected a cached computed var `submission_count` decorated with "
        "`@rx.var` or `@rx.var(cache=True)` that returns `len(self.submissions)`. "
        "Not found on any rx.State subclass."
    )


def test_rx_form_with_on_submit_present(parsed_modules):
    matches = _find_rx_form_calls_with_on_submit(parsed_modules)
    assert matches, (
        "Expected at least one `rx.form(...)` (or `rx.form.root(...)`) call with "
        "an `on_submit=` handler. None found in the project source."
    )


# ---------------------------------------------------------------------------
# HTTP scan tests (require the Reflex dev server to be running)
# ---------------------------------------------------------------------------


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _kill_listeners_on_port(port: int) -> None:
    """Best-effort: kill any process bound to the given port using lsof/fuser."""
    lsof = shutil.which("lsof")
    if lsof:
        try:
            result = subprocess.run(
                [lsof, "-tiTCP", f"-i:{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for pid_str in result.stdout.split():
                try:
                    os.kill(int(pid_str), signal.SIGTERM)
                except (ProcessLookupError, ValueError, PermissionError):
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    fuser = shutil.which("fuser")
    if fuser:
        try:
            subprocess.run(
                [fuser, "-k", f"{port}/tcp"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass


@pytest.fixture(scope="module")
def reflex_server():
    """Start `uv run reflex run` in the project directory and tear it down."""
    uv_bin = shutil.which("uv")
    assert uv_bin is not None, "uv binary not found in PATH; required to start Reflex."

    # Make sure no leftover server is listening before we start ours.
    for port in (FRONTEND_PORT, BACKEND_PORT):
        if _port_open(port):
            _kill_listeners_on_port(port)
            time.sleep(2)

    log_path = "/tmp/reflex_final_state.log"
    log_file = open(log_path, "wb")
    proc = subprocess.Popen(
        [uv_bin, "run", "reflex", "run", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # become process group leader for clean kill
    )

    # Wait for both frontend and backend ports to be reachable.
    deadline = time.time() + 360  # first run compiles Node assets; allow time
    frontend_ready = False
    backend_ready = False
    last_err = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            log_file.flush()
            with open(log_path, "rb") as f:
                tail = f.read()[-4000:].decode("utf-8", errors="replace")
            pytest.fail(
                f"`uv run reflex run` exited early with code {proc.returncode}.\n"
                f"--- log tail ---\n{tail}"
            )
        if not backend_ready and _port_open(BACKEND_PORT):
            backend_ready = True
        if not frontend_ready and _port_open(FRONTEND_PORT):
            # Confirm the HTTP server actually responds, not just that the port is bound.
            try:
                with urllib.request.urlopen(FRONTEND_URL, timeout=5) as resp:
                    if resp.status == 200:
                        frontend_ready = True
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
        if frontend_ready and backend_ready:
            break
        time.sleep(2)

    if not (frontend_ready and backend_ready):
        log_file.flush()
        with open(log_path, "rb") as f:
            tail = f.read()[-4000:].decode("utf-8", errors="replace")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        pytest.fail(
            f"Reflex dev server did not become ready within the timeout "
            f"(frontend_ready={frontend_ready}, backend_ready={backend_ready}, "
            f"last_http_error={last_err!r}).\n"
            f"--- log tail ---\n{tail}"
        )

    try:
        yield FRONTEND_URL
    finally:
        # Teardown: kill the entire process group, then sweep both ports.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        for port in (FRONTEND_PORT, BACKEND_PORT):
            if _port_open(port):
                _kill_listeners_on_port(port)
        try:
            log_file.close()
        except Exception:  # noqa: BLE001
            pass


def _fetch(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="replace")


def _collect_served_payload(base_url: str) -> str:
    """Fetch `/` plus all referenced same-origin JS/CSS assets and concatenate."""
    html = _fetch(base_url)
    parsed_base = urllib.parse.urlsplit(base_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    asset_paths = set()
    for match in re.finditer(r'''(?:src|href)\s*=\s*["']([^"']+)["']''', html):
        asset = match.group(1)
        if asset.endswith((".js", ".css", ".mjs")) or "/_next/" in asset:
            asset_paths.add(asset)

    combined = [html]
    for path in asset_paths:
        if path.startswith("http://") or path.startswith("https://"):
            asset_url = path
        elif path.startswith("//"):
            asset_url = f"{parsed_base.scheme}:{path}"
        elif path.startswith("/"):
            asset_url = f"{base_origin}{path}"
        else:
            asset_url = urllib.parse.urljoin(base_url, path)
        # Skip cross-origin assets.
        if not asset_url.startswith(base_origin):
            continue
        try:
            combined.append(_fetch(asset_url, timeout=30))
        except Exception:  # noqa: BLE001
            # Some chunks may legitimately be unreachable at this stage; ignore.
            continue
    return "\n".join(combined)


def _payload_contains_input_name(payload: str, name: str) -> bool:
    # Reflex emits these as React props; in serialized JS they may appear as
    # name="x", name:"x", or "name":"x". Accept any of those forms.
    patterns = [
        rf'name\s*=\s*"{re.escape(name)}"',
        rf"name\s*=\s*'{re.escape(name)}'",
        rf'name\s*:\s*"{re.escape(name)}"',
        rf"name\s*:\s*'{re.escape(name)}'",
        rf'"name"\s*:\s*"{re.escape(name)}"',
    ]
    return any(re.search(p, payload) for p in patterns)


def test_frontend_serves_form_input_names(reflex_server):
    payload = _collect_served_payload(reflex_server)
    for field in ("name", "email", "message"):
        assert _payload_contains_input_name(payload, field), (
            f'Expected the served `/` page (HTML + referenced JS chunks) to '
            f'contain an input with name="{field}". Not found.'
        )


def test_frontend_serves_submit_button_text(reflex_server):
    payload = _collect_served_payload(reflex_server)
    assert re.search(r"submit", payload, re.IGNORECASE), (
        "Expected the served `/` page to contain visible Submit button text "
        "(case-insensitive match for 'submit'). Not found in HTML or JS chunks."
    )
