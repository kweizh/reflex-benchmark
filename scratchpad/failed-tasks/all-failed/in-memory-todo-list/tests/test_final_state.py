import os
import re
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/myproject"
REFLEX_LOG_PATH = "/tmp/reflex.log"

FRONTEND_PORT = 3000
BACKEND_PORT = 8000


# ---------- helpers ----------

def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_port(port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(port):
            return True
        time.sleep(1.0)
    return False


def _collect_py_sources() -> str:
    py_sources = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [
            d for d in dirs
            if d not in (".venv", "__pycache__", ".web", ".git",
                         "node_modules", "alembic")
        ]
        for fn in files:
            if fn.endswith(".py"):
                py_sources.append(os.path.join(root, fn))
    combined = ""
    for path in py_sources:
        try:
            combined += "\n" + Path(path).read_text(errors="replace")
        except OSError:
            continue
    return combined


def _collect_compiled_frontend_text() -> str:
    """Collect text from the live frontend page plus any static asset files
    under .web/_static, so we can search for literal strings the executor was
    supposed to put into the UI."""
    parts = []
    # 1. The live HTML returned by GET /
    try:
        r = requests.get(f"http://localhost:{FRONTEND_PORT}/", timeout=10)
        if r.status_code == 200:
            parts.append(r.text)
    except Exception:
        pass

    # 2. Any .js/.html/.json under .web (the compiled Next.js output)
    web_root = os.path.join(PROJECT_DIR, ".web")
    if os.path.isdir(web_root):
        for root, dirs, files in os.walk(web_root):
            # skip node_modules inside .web to avoid library noise
            dirs[:] = [d for d in dirs if d != "node_modules"]
            for fn in files:
                if fn.endswith((".js", ".html", ".json")):
                    fp = os.path.join(root, fn)
                    try:
                        parts.append(Path(fp).read_text(errors="replace"))
                    except OSError:
                        continue
    return "\n".join(parts)


# ---------- fixtures ----------

@pytest.fixture(scope="session", autouse=True)
def _no_stale_ports():
    assert not _port_open(FRONTEND_PORT), (
        f"Port {FRONTEND_PORT} is already in use before the verifier started the "
        f"Reflex server. The task description requires the candidate to terminate "
        f"any background `reflex run` processes after they finish."
    )
    assert not _port_open(BACKEND_PORT), (
        f"Port {BACKEND_PORT} is already in use before the verifier started the "
        f"Reflex server."
    )


@pytest.fixture(scope="session")
def reflex_server(xprocess):
    if os.path.exists(REFLEX_LOG_PATH):
        os.remove(REFLEX_LOG_PATH)
    log_fp = open(REFLEX_LOG_PATH, "w")

    class Starter(ProcessStarter):
        name = "reflex_server"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
            "stdout": log_fp,
            "stderr": subprocess.STDOUT,
        }
        timeout = 360
        terminate_on_interrupt = True

        def startup_check(self):
            return _port_open(FRONTEND_PORT) and _port_open(BACKEND_PORT)

    xprocess.ensure(Starter.name, Starter)
    assert _wait_for_port(FRONTEND_PORT, 60), "Frontend port did not become ready."
    assert _wait_for_port(BACKEND_PORT, 60), "Backend port did not become ready."

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    log_fp.close()


# ---------- server-level checks ----------

def test_frontend_reachable(reflex_server):
    last_exc = None
    for _ in range(30):
        try:
            r = requests.get(f"http://localhost:{FRONTEND_PORT}/", timeout=10)
            if r.status_code == 200 and r.text:
                body = r.text.lower()
                assert "<html" in body or "<!doctype" in body, (
                    f"Frontend at port {FRONTEND_PORT} did not return HTML."
                )
                return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        time.sleep(2)
    raise AssertionError(
        f"Frontend at http://localhost:{FRONTEND_PORT}/ never returned HTTP 200. "
        f"Last exception: {last_exc!r}"
    )


def test_compiled_frontend_contains_add_and_total(reflex_server):
    text = _collect_compiled_frontend_text()
    assert text, (
        "Could not collect any compiled frontend text. Did the Reflex frontend "
        "actually start and serve `GET /`?"
    )
    assert "Add" in text, (
        "Could not find the literal string 'Add' in the compiled frontend "
        "(HTML body of `GET /` plus .web/_static assets). The task requires "
        "an 'Add' button on the index page."
    )
    assert "Total:" in text, (
        "Could not find the literal string 'Total:' in the compiled frontend. "
        "The task requires the total to be rendered as 'Total: N'."
    )


def test_no_immutable_state_error_in_logs(reflex_server):
    assert os.path.exists(REFLEX_LOG_PATH), (
        f"Expected Reflex log at {REFLEX_LOG_PATH}."
    )
    log_text = Path(REFLEX_LOG_PATH).read_text(errors="replace")
    assert "ImmutableStateError" not in log_text, (
        "Reflex backend logged an ImmutableStateError."
    )
    assert "Background task StateProxy is immutable" not in log_text, (
        "Reflex backend logged the StateProxy-immutable error."
    )


# ---------- source-code contract checks ----------

def test_source_declares_new_item_base_var():
    combined = _collect_py_sources()
    assert combined, f"No Python source files found under {PROJECT_DIR}."
    assert re.search(
        r"\bnew_item\s*:\s*str\s*=\s*(?:\"\"|'')",
        combined,
    ), (
        "Could not find a `new_item: str = \"\"` base var declaration on any "
        "State class. The State must expose `new_item` defaulting to the empty "
        "string."
    )


def test_source_declares_items_base_var():
    combined = _collect_py_sources()
    assert re.search(
        r"\bitems\s*:\s*list\s*\[\s*str\s*\]\s*=\s*\[\s*\]",
        combined,
    ), (
        "Could not find an `items: list[str] = []` base var declaration on any "
        "State class. The State must expose `items` defaulting to an empty list."
    )


def test_source_uses_rx_foreach_over_items():
    combined = _collect_py_sources()
    assert re.search(
        r"rx\.foreach\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\.items\b",
        combined,
    ), (
        "Could not find a call to `rx.foreach(<State>.items, ...)`. The items "
        "must be rendered with `rx.foreach`."
    )


def test_source_has_add_handler():
    combined = _collect_py_sources()
    has_append = (
        ("self.items.append(self.new_item)" in combined)
        or re.search(
            r"self\.items\s*=\s*self\.items\s*\+\s*\[\s*self\.new_item\s*\]",
            combined,
        )
        or re.search(
            r"self\.items\s*\+=\s*\[\s*self\.new_item\s*\]",
            combined,
        )
    )
    assert has_append, (
        "Could not find an event handler that appends `self.new_item` to "
        "`self.items` (e.g. `self.items.append(self.new_item)`)."
    )
    assert re.search(
        r"self\.new_item\s*=\s*(?:\"\"|'')",
        combined,
    ), (
        "Could not find an assignment that clears `self.new_item` back to the "
        "empty string after adding (e.g. `self.new_item = \"\"`)."
    )


def test_source_has_remove_by_index_handler():
    combined = _collect_py_sources()

    # The handler must accept an `int` parameter (the index).
    accepts_int_param = re.search(r":\s*int\b", combined) is not None
    assert accepts_int_param, (
        "Could not find an event handler that accepts an `int` parameter. The "
        "remove handler must take the integer index of the item to remove."
    )

    # The handler must remove an element from self.items by index.
    removes_by_index = bool(
        re.search(r"del\s+self\.items\s*\[", combined)
        or re.search(r"self\.items\.pop\s*\(", combined)
    )
    assert removes_by_index, (
        "Could not find a remove-by-index operation on `self.items` "
        "(expected `del self.items[index]` or `self.items.pop(index)`)."
    )


def test_source_has_cached_total_computed_var():
    combined = _collect_py_sources()
    # Look for either @rx.cached_var or @rx.var(cache=True) directly followed by
    # `def total(`, optionally across blank/comment lines.
    pattern = re.compile(
        r"@rx\.(?:cached_var\b|var\s*\(\s*[^)]*cache\s*=\s*True[^)]*\))"
        r"(?:[ \t]*\r?\n[ \t]*)+def\s+total\s*\(",
        re.MULTILINE,
    )
    assert pattern.search(combined), (
        "Could not find a cached computed var named `total` (expected "
        "`@rx.var(cache=True)` or `@rx.cached_var` directly above `def total(...)`)."
    )

    # The total method must return len(self.items). Search for the literal call
    # anywhere in the combined source.
    assert re.search(r"return\s+len\s*\(\s*self\.items\s*\)", combined), (
        "Could not find `return len(self.items)` in the source. The `total` "
        "computed var must return the length of `self.items`."
    )
