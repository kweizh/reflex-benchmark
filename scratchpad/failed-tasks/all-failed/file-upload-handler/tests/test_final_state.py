"""Final-state tests for the Reflex file-upload-handler task.

The tests run with system python3 (Reflex is NOT importable here). We rely on:
- AST inspection of the user's Python source files.
- subprocess + `uv run reflex run` to launch the live app and exercise HTTP.
- socket connectivity checks for the Reflex frontend (port 3000) and backend
  (port 8000).
- All background processes are killed in fixture teardown.
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
from pathlib import Path
from typing import Iterator

import pytest
import requests

PROJECT_DIR = Path("/home/user/myproject")
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
UPLOAD_DIR_DEFAULT = PROJECT_DIR / "uploaded_files"


# ---------------------------------------------------------------------------
# Source discovery and AST helpers
# ---------------------------------------------------------------------------


def _python_sources() -> list[Path]:
    """Collect all .py files in the project, excluding the .web build dir and venv."""
    excluded_parts = {".web", ".venv", "__pycache__", "uploaded_files", ".git"}
    files: list[Path] = []
    for path in PROJECT_DIR.rglob("*.py"):
        if any(part in excluded_parts for part in path.parts):
            continue
        files.append(path)
    return files


def _parse_sources() -> list[tuple[Path, ast.Module]]:
    parsed: list[tuple[Path, ast.Module]] = []
    for src in _python_sources():
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        parsed.append((src, tree))
    return parsed


def _is_rx_attr(node: ast.AST, attr_name: str) -> bool:
    """Return True if `node` is the Attribute `rx.<attr_name>`."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attr_name
        and isinstance(node.value, ast.Name)
        and node.value.id == "rx"
    )


def _kw_dict(node: ast.Call) -> dict[str, ast.expr]:
    return {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}


# ---------------------------------------------------------------------------
# Static (AST) tests
# ---------------------------------------------------------------------------


def test_project_directory_exists():
    assert PROJECT_DIR.is_dir(), (
        f"Reflex project directory {PROJECT_DIR} does not exist."
    )


def test_rx_upload_call_has_required_kwargs():
    """rx.upload(id='upload1', accept={'text/plain': ['.txt'], 'image/png': ['.png']})"""
    parsed = _parse_sources()
    assert parsed, f"No Python sources found in {PROJECT_DIR}."

    found = False
    for _src, tree in parsed:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_rx_attr(node.func, "upload"):
                continue
            kwargs = _kw_dict(node)

            id_node = kwargs.get("id")
            if not (
                isinstance(id_node, ast.Constant) and id_node.value == "upload1"
            ):
                continue

            accept_node = kwargs.get("accept")
            if not isinstance(accept_node, ast.Dict):
                continue

            accept_map: dict[str, list[str]] = {}
            ok = True
            for key_node, val_node in zip(accept_node.keys, accept_node.values):
                if not (
                    isinstance(key_node, ast.Constant)
                    and isinstance(key_node.value, str)
                ):
                    ok = False
                    break
                if not isinstance(val_node, (ast.List, ast.Tuple)):
                    ok = False
                    break
                vals: list[str] = []
                for elt in val_node.elts:
                    if not (
                        isinstance(elt, ast.Constant)
                        and isinstance(elt.value, str)
                    ):
                        ok = False
                        break
                    vals.append(elt.value)
                if not ok:
                    break
                accept_map[key_node.value] = vals
            if not ok:
                continue

            if (
                accept_map.get("text/plain") == [".txt"]
                and accept_map.get("image/png") == [".png"]
            ):
                found = True
                break
        if found:
            break

    assert found, (
        "Could not find an `rx.upload(...)` call with `id=\"upload1\"` and "
        "`accept={\"text/plain\": [\".txt\"], \"image/png\": [\".png\"]}` "
        "in the project sources."
    )


def test_uploaded_files_state_var_declared():
    """State class must declare `uploaded_files: list[str] = []`."""
    parsed = _parse_sources()
    assert parsed, f"No Python sources found in {PROJECT_DIR}."

    found = False
    for _src, tree in parsed:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, ast.AnnAssign):
                    continue
                if not (
                    isinstance(item.target, ast.Name)
                    and item.target.id == "uploaded_files"
                ):
                    continue
                # Annotation must be list[str]
                ann = item.annotation
                is_list_str = False
                if (
                    isinstance(ann, ast.Subscript)
                    and isinstance(ann.value, ast.Name)
                    and ann.value.id in ("list", "List")
                ):
                    slc = ann.slice
                    if (
                        isinstance(slc, ast.Name) and slc.id == "str"
                    ):
                        is_list_str = True
                if not is_list_str:
                    continue
                # Default must be [] (empty list literal)
                if not (
                    isinstance(item.value, ast.List) and len(item.value.elts) == 0
                ):
                    continue
                found = True
                break
            if found:
                break
        if found:
            break

    assert found, (
        "Could not find a state class declaring "
        "`uploaded_files: list[str] = []`."
    )


def test_handle_upload_handler_signature_and_body():
    """Async event handler `handle_upload(self, files: list[rx.UploadFile])`
    must `await file.read()` and call `rx.get_upload_dir()`."""
    parsed = _parse_sources()
    assert parsed, f"No Python sources found in {PROJECT_DIR}."

    found = False
    for _src, tree in parsed:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, ast.AsyncFunctionDef):
                    continue
                if item.name != "handle_upload":
                    continue

                # Signature: (self, files: list[rx.UploadFile])
                args = item.args.args
                if len(args) < 2:
                    continue
                if args[0].arg != "self":
                    continue
                if args[1].arg != "files":
                    continue
                ann = args[1].annotation
                # list[rx.UploadFile] or List[rx.UploadFile]
                if not (
                    isinstance(ann, ast.Subscript)
                    and isinstance(ann.value, ast.Name)
                    and ann.value.id in ("list", "List")
                ):
                    continue
                inner = ann.slice
                if not _is_rx_attr(inner, "UploadFile"):
                    continue

                # Body must contain `await <expr>.read()` and `rx.get_upload_dir()`
                has_await_read = False
                has_get_upload_dir = False
                for sub in ast.walk(item):
                    if (
                        isinstance(sub, ast.Await)
                        and isinstance(sub.value, ast.Call)
                        and isinstance(sub.value.func, ast.Attribute)
                        and sub.value.func.attr == "read"
                    ):
                        has_await_read = True
                    if (
                        isinstance(sub, ast.Call)
                        and _is_rx_attr(sub.func, "get_upload_dir")
                    ):
                        has_get_upload_dir = True

                if has_await_read and has_get_upload_dir:
                    found = True
                    break
            if found:
                break
        if found:
            break

    assert found, (
        "Could not find an async `handle_upload(self, files: list[rx.UploadFile])` "
        "method whose body both awaits `file.read()` and calls "
        "`rx.get_upload_dir()`."
    )


def test_rx_foreach_iterates_uploaded_files():
    """An rx.foreach(...) call must iterate State.uploaded_files (or self.uploaded_files)."""
    parsed = _parse_sources()
    assert parsed, f"No Python sources found in {PROJECT_DIR}."

    found = False
    for _src, tree in parsed:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_rx_attr(node.func, "foreach"):
                continue
            if not node.args:
                continue
            iterable = node.args[0]
            if (
                isinstance(iterable, ast.Attribute)
                and iterable.attr == "uploaded_files"
            ):
                found = True
                break
        if found:
            break

    assert found, (
        "Could not find an `rx.foreach(<State>.uploaded_files, ...)` call "
        "rendering the dynamic list of uploaded filenames."
    )


# ---------------------------------------------------------------------------
# Live-server fixtures and tests
# ---------------------------------------------------------------------------


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def _kill_by_port(port: int) -> None:
    """Best-effort: kill any process holding `port` via `fuser` or `lsof`."""
    for cmd in (
        ["fuser", "-k", f"{port}/tcp"],
        ["bash", "-lc", f"lsof -ti :{port} | xargs -r kill -9"],
    ):
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
        except Exception:
            pass


@pytest.fixture(scope="session")
def reflex_app() -> Iterator[None]:
    """Start the Reflex app via `uv run reflex run` in the background."""
    if not PROJECT_DIR.is_dir():
        pytest.skip(f"Project directory {PROJECT_DIR} not found.")

    # Ensure ports are free before starting.
    _kill_by_port(FRONTEND_PORT)
    _kill_by_port(BACKEND_PORT)

    # Clean previous verification artifacts.
    for fname in ("zealt_check.txt",):
        p = UPLOAD_DIR_DEFAULT / fname
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    env = os.environ.copy()
    env.setdefault("REFLEX_TELEMETRY_ENABLED", "false")

    uv = shutil.which("uv")
    assert uv is not None, "uv is not available in PATH; cannot start Reflex app."

    proc = subprocess.Popen(
        [uv, "run", "reflex", "run", "--loglevel", "info"],
        cwd=str(PROJECT_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    try:
        # Wait for both ports to come up. Reflex first-run may need to compile.
        deadline = time.time() + 300
        backend_up = False
        frontend_up = False
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(
                    f"`reflex run` exited prematurely with code {proc.returncode}."
                )
            backend_up = backend_up or _port_open("127.0.0.1", BACKEND_PORT)
            frontend_up = frontend_up or _port_open("127.0.0.1", FRONTEND_PORT)
            if backend_up and frontend_up:
                break
            time.sleep(2)

        if not backend_up:
            pytest.fail(
                f"Reflex backend did not start on port {BACKEND_PORT} within timeout."
            )
        if not frontend_up:
            pytest.fail(
                f"Reflex frontend did not start on port {FRONTEND_PORT} within timeout."
            )

        # Allow the dev server a moment to fully serve assets.
        time.sleep(3)
        yield None
    finally:
        # Kill the entire process group to make sure child node/uvicorn die too.
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

        # Defensive: free the ports even if the dev server forked detached children.
        _kill_by_port(FRONTEND_PORT)
        _kill_by_port(BACKEND_PORT)


def test_frontend_serves_upload_component(reflex_app):
    """The compiled frontend HTML/JS should include a file <input> with the
    configured accept types and a hint of the dynamic uploaded_files state.
    """
    resp = requests.get(f"http://127.0.0.1:{FRONTEND_PORT}/", timeout=30)
    assert resp.status_code == 200, (
        f"Frontend root returned status {resp.status_code}."
    )
    body = resp.text

    # Accept types from rx.upload accept mapping should appear in compiled JS/HTML.
    accept_has_txt = ".txt" in body or "text/plain" in body
    accept_has_png = ".png" in body or "image/png" in body
    assert accept_has_txt and accept_has_png, (
        "Expected the served frontend to reference the configured upload accept "
        "types ('.txt'/'text/plain' and '.png'/'image/png')."
    )

    # The state var name should be embedded somewhere in the compiled bundle.
    # If the homepage HTML alone does not mention it, follow up by fetching the
    # main JS chunks linked from the page.
    if "uploaded_files" not in body:
        scripts = re.findall(r'src="([^"]+\.js)"', body)
        joined = ""
        for s in scripts[:10]:
            url = s if s.startswith("http") else f"http://127.0.0.1:{FRONTEND_PORT}{s}"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    joined += r.text
            except requests.RequestException:
                continue
        assert "uploaded_files" in body or "uploaded_files" in joined, (
            "Could not find any reference to the `uploaded_files` state var in "
            "the compiled frontend bundle."
        )


def test_backend_upload_persists_file(reflex_app):
    """POST a small text file to the Reflex `/_upload` endpoint and verify it
    is written under `rx.get_upload_dir()`, which defaults to
    `<project>/uploaded_files`.
    """
    upload_dir = Path(os.environ.get("REFLEX_UPLOADED_FILES_DIR") or UPLOAD_DIR_DEFAULT)
    target = upload_dir / "zealt_check.txt"
    if target.exists():
        target.unlink()

    content = b"hello-from-zealt"
    files = {"files": ("zealt_check.txt", content, "text/plain")}
    # Reflex multipart upload endpoint expects a header identifying the upload id
    # and the target state event handler; we send the conventional header used by
    # `rx.upload_files` so the server routes it correctly.
    headers = {
        "Reflex-Client-Token": "zealt-test-client",
    }
    url = f"http://127.0.0.1:{BACKEND_PORT}/_upload"

    try:
        resp = requests.post(url, files=files, headers=headers, timeout=30)
    except requests.RequestException as exc:
        pytest.fail(f"POST to {url} raised {exc!r}.")

    assert resp.status_code < 500, (
        f"Reflex `/_upload` returned server error {resp.status_code}: "
        f"{resp.text[:200]}"
    )

    # Allow filesystem flush.
    deadline = time.time() + 15
    while time.time() < deadline and not target.exists():
        time.sleep(0.5)

    assert target.exists(), (
        f"Expected uploaded file at {target} after POST /_upload, but it was "
        "not created. The handler is not persisting files via "
        "rx.get_upload_dir()."
    )
    assert target.read_bytes() == content, (
        f"Uploaded file contents at {target} differ from what was POSTed."
    )

    # Cleanup
    try:
        target.unlink()
    except OSError:
        pass
