"""Final-state verification for the realtime-character-counter Reflex task.

These tests are executed by the system python3. They MUST NOT assume that the
`reflex` package is importable in the system Python — the project itself is
managed by `uv` inside `/home/user/myproject`. Use `subprocess` + `uv run` to
interact with the project, and parse `.py` source files with `ast`/regex for
static checks.
"""

import ast
import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests


PROJECT_DIR = "/home/user/myproject"
FRONTEND_URL = "http://localhost:3000/"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(1.0)
    return False


def _iter_py_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip virtualenvs, build outputs, hidden directories, and node_modules
        dirnames[:] = [
            d for d in dirnames
            if d
            not in {
                ".venv",
                "venv",
                ".web",
                "__pycache__",
                "node_modules",
                ".git",
                "alembic",
                "build",
                "dist",
            }
        ]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _collect_rx_var_methods():
    """Return list of (file_path, method_name, source_segment) for every
    function decorated with @rx.var (with or without args)."""
    hits = []
    for path in _iter_py_files(PROJECT_DIR):
        try:
            source = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                dec_src = ast.get_source_segment(source, dec) or ""
                # Match @rx.var, @rx.var(...), @reflex.var, etc.
                if re.search(r"\b(rx|reflex)\.var\b", dec_src):
                    body_src = ast.get_source_segment(source, node) or ""
                    hits.append((path, node.name, body_src))
                    break
    return hits


# ---------------------------------------------------------------------------
# Fixtures: start the dev server for the duration of the test session.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def reflex_server():
    """Start `uv run reflex run` in the background and tear it down after."""
    # Pre-flight: make sure nothing else is hanging onto the ports.
    subprocess.run(
        ["pkill", "-f", "reflex run"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)

    log_path = os.path.join(PROJECT_DIR, "_reflex_server.log")
    log_fh = open(log_path, "w", encoding="utf-8")

    env = os.environ.copy()
    # Reflex emits less noise / no telemetry prompts in CI.
    env.setdefault("TELEMETRY_ENABLED", "false")

    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )

    try:
        backend_ready = _wait_for_port(BACKEND_PORT, timeout=300.0)
        frontend_ready = _wait_for_port(FRONTEND_PORT, timeout=300.0)
        if not (backend_ready and frontend_ready):
            log_fh.flush()
            log_tail = ""
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    log_tail = f.read()[-4000:]
            except OSError:
                pass
            pytest.fail(
                f"Reflex dev server failed to start "
                f"(backend_ready={backend_ready}, frontend_ready={frontend_ready}).\n"
                f"--- server log tail ---\n{log_tail}"
            )
        # Give Next.js a moment to finish first-page compilation.
        time.sleep(3.0)
        yield proc
    finally:
        # Tear down: kill the process group, then kill any stragglers.
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
        subprocess.run(
            ["pkill", "-f", "reflex run"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["pkill", "-f", "next-server"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log_fh.close()


# ---------------------------------------------------------------------------
# Static project structure checks
# ---------------------------------------------------------------------------


def test_rxconfig_exists():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), (
        f"Expected Reflex config at {rxconfig}. Did the executor run "
        "'uv run reflex init --template blank'?"
    )
    text = Path(rxconfig).read_text(encoding="utf-8")
    assert "rx.Config" in text or "reflex.Config" in text, (
        "rxconfig.py must instantiate rx.Config(...)."
    )


def test_app_module_imports_reflex():
    """At least one .py file in the project must import reflex as rx."""
    found = False
    for path in _iter_py_files(PROJECT_DIR):
        if path.endswith("rxconfig.py"):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if re.search(r"^\s*import\s+reflex\s+as\s+rx\b", text, re.MULTILINE):
            found = True
            break
    assert found, (
        "No Reflex app module found that imports 'reflex as rx' under "
        f"{PROJECT_DIR}."
    )


def test_two_rx_var_computed_methods_exist():
    methods = _collect_rx_var_methods()
    assert len(methods) >= 2, (
        f"Expected at least two @rx.var-decorated methods in the project, "
        f"but found {len(methods)}: {[m[1] for m in methods]}"
    )

    # One method should compute character count (must reference len(...content...)).
    char_method = None
    word_method = None
    for path, name, src in methods:
        # Character count: contains `len(` and references `self.content` but does NOT split.
        has_len = re.search(r"\blen\s*\(", src) is not None
        references_content = re.search(r"self\.content\b", src) is not None
        uses_split = re.search(r"self\.content\s*\.\s*split\b", src) is not None
        if has_len and references_content and not uses_split and char_method is None:
            char_method = (path, name)
        if has_len and uses_split and word_method is None:
            word_method = (path, name)

    assert char_method is not None, (
        "Could not find a @rx.var-decorated method whose body counts characters "
        "of `self.content` (e.g. `return len(self.content)`). "
        f"Candidates inspected: {[m[1] for m in methods]}"
    )
    assert word_method is not None, (
        "Could not find a @rx.var-decorated method whose body counts whitespace-"
        "separated words of `self.content` (e.g. `return len(self.content.split())`). "
        f"Candidates inspected: {[m[1] for m in methods]}"
    )
    assert char_method[1] != word_method[1] or char_method[0] != word_method[0], (
        "Character-count and word-count must be implemented as two distinct "
        "computed vars."
    )


def test_text_area_uses_required_id():
    """Search the project source for an rx.text_area(...) call that sets id='content_input'."""
    pattern = re.compile(
        r"rx\.text_area\s*\([^)]*\bid\s*=\s*[\"']content_input[\"']",
        re.DOTALL,
    )
    found = False
    for path in _iter_py_files(PROJECT_DIR):
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pattern.search(text):
            found = True
            break
    assert found, (
        "Could not find an rx.text_area(...) call with id=\"content_input\" "
        "anywhere in the project source."
    )


# ---------------------------------------------------------------------------
# Runtime checks (require the dev server)
# ---------------------------------------------------------------------------


def test_backend_is_listening(reflex_server):
    assert _wait_for_port(BACKEND_PORT, timeout=5.0), (
        f"Reflex backend was not reachable on port {BACKEND_PORT}."
    )


def test_frontend_returns_200_with_expected_markers(reflex_server):
    last_exc = None
    body = ""
    for _ in range(30):
        try:
            resp = requests.get(FRONTEND_URL, timeout=10)
            if resp.status_code == 200:
                body = resp.text
                break
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(2.0)
    else:
        pytest.fail(
            f"Frontend at {FRONTEND_URL} never returned 200. Last error: {last_exc!r}"
        )

    # The compiled Next.js HTML should mention the textarea id and the static
    # labels. Reflex sometimes inlines labels into the JS bundle; if the
    # markers aren't in the initial HTML, follow up by checking the linked
    # _next chunk(s) referenced from <script src=...>.
    haystacks = [body]
    chunk_urls = set(
        re.findall(r'src="(/_next/static/[^"]+\.js)"', body)
    )
    for chunk in list(chunk_urls)[:25]:
        try:
            chunk_resp = requests.get(
                f"http://localhost:{FRONTEND_PORT}{chunk}", timeout=10
            )
            if chunk_resp.status_code == 200:
                haystacks.append(chunk_resp.text)
        except requests.RequestException:
            continue

    combined = "\n".join(haystacks)
    assert "content_input" in combined, (
        "Expected the textarea id 'content_input' to appear in the rendered page "
        "or its JS bundle."
    )
    assert "Characters:" in combined, (
        "Expected the literal 'Characters:' label to be rendered by the page."
    )
    assert "Words:" in combined, (
        "Expected the literal 'Words:' label to be rendered by the page."
    )
