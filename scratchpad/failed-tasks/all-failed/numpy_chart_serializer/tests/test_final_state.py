import os
import re
import socket
import subprocess
import time
from typing import Iterable, List

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/numpy_chart_serializer"
FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"


# ---------- helpers ----------


def _iter_py_files(root: str) -> Iterable[str]:
    skip_dirs = {".web", ".venv", "venv", "__pycache__", ".git", "node_modules"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _read_all_py_sources(root: str) -> List[tuple]:
    out = []
    for path in _iter_py_files(root):
        try:
            with open(path, "r", encoding="utf-8") as f:
                out.append((path, f.read()))
        except (OSError, UnicodeDecodeError):
            continue
    return out


def _port_listening(port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect(("127.0.0.1", port))
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False
        return True


def _wait_for(url: str, timeout: float, predicate=None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=5)
            if predicate is None:
                if r.status_code == 200:
                    return True
            else:
                if predicate(r):
                    return True
        except requests.RequestException:
            pass
        time.sleep(2.0)
    return False


def _force_free_ports():
    # Best-effort cleanup so leftover servers from previous runs cannot pollute
    # the verification environment.
    for cmd in (
        ["bash", "stop.sh"],
        ["pkill", "-f", "reflex run"],
        ["pkill", "-f", "next dev"],
        ["fuser", "-k", "3000/tcp"],
        ["fuser", "-k", "8000/tcp"],
    ):
        try:
            if cmd[0] == "bash":
                if not os.path.isfile(os.path.join(PROJECT_DIR, "stop.sh")):
                    continue
                subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, timeout=20)
            else:
                subprocess.run(cmd, capture_output=True, timeout=20)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    time.sleep(1.0)


# ---------- fixtures ----------


@pytest.fixture(scope="session")
def reflex_app(xprocess):
    _force_free_ports()

    start_script = os.path.join(PROJECT_DIR, "start.sh")
    assert os.path.isfile(start_script), (
        f"Expected start script at {start_script}; the task description requires bash start.sh."
    )

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["bash", "start.sh"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 360
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend ping is the most reliable readiness signal for Reflex.
            try:
                r = requests.get(f"{BACKEND_URL}/ping/", timeout=3)
            except requests.RequestException:
                return False
            return r.status_code == 200 and "pong" in r.text.lower()

    xprocess.ensure(Starter.name, Starter)

    # Wait for the frontend (Next.js dev) too — it boots after the backend.
    assert _wait_for(f"{FRONTEND_URL}/", timeout=240), (
        "Frontend on http://localhost:3000/ did not become ready within 240 seconds."
    )

    yield

    # ---- teardown ----
    info = xprocess.getinfo(Starter.name)
    try:
        info.terminate()
    except Exception:
        pass
    _force_free_ports()


@pytest.fixture(scope="session")
def app_log_path(reflex_app):
    # xprocess stores stdout/stderr in its data dir; we also let the start script
    # tee its own log if desired. The fixture exists so tests can declare the
    # ordering dependency on reflex_app explicitly.
    return None


# ---------- source-code-shape tests ----------

_STATE_VAR_PATTERN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:numpy\.ndarray|np\.ndarray)\b",
    re.MULTILINE,
)

_SERIALIZER_PATTERN = re.compile(
    r"@rx\.serializer\s*\r?\n\s*def\s+\w+\s*\([^)]*?:\s*(?:numpy\.ndarray|np\.ndarray)[^)]*\)"
    r"\s*->\s*(?:list\s*\[\s*dict\s*\[\s*str\s*,\s*float\s*\]\s*\]|List\s*\[\s*Dict\s*\[\s*str\s*,\s*float\s*\]\s*\])",
    re.MULTILINE,
)


def test_state_var_typed_as_ndarray():
    """An rx.State subclass must declare a non-underscore base var typed as numpy.ndarray."""
    sources = _read_all_py_sources(PROJECT_DIR)
    assert sources, f"No Python source files were found under {PROJECT_DIR}."

    matched = []
    for path, src in sources:
        for m in _STATE_VAR_PATTERN.finditer(src):
            name = m.group(1)
            if name.startswith("_"):
                continue
            matched.append((path, name))

    assert matched, (
        "Could not find any base state var annotated with `numpy.ndarray` (or `np.ndarray`). "
        "The task requires a synchronized (non-underscore) state field typed as numpy.ndarray."
    )


def test_serializer_registered_for_ndarray():
    """A function decorated with @rx.serializer must accept numpy.ndarray and return list[dict[str, float]]."""
    sources = _read_all_py_sources(PROJECT_DIR)
    assert sources, f"No Python source files were found under {PROJECT_DIR}."

    found = False
    for path, src in sources:
        if _SERIALIZER_PATTERN.search(src):
            found = True
            break

    assert found, (
        "Could not find a function decorated with @rx.serializer that takes a numpy.ndarray "
        "argument and returns list[dict[str, float]]. The task requires this exact contract."
    )


# ---------- runtime HTTP tests ----------


def test_backend_ping_returns_pong(reflex_app):
    r = requests.get(f"{BACKEND_URL}/ping/", timeout=10)
    assert r.status_code == 200, (
        f"GET {BACKEND_URL}/ping/ expected 200, got {r.status_code}: {r.text!r}"
    )
    assert "pong" in r.text.lower(), (
        f"GET {BACKEND_URL}/ping/ expected body to contain 'pong', got {r.text!r}"
    )


def test_frontend_renders_without_vartypeerror(reflex_app):
    r = requests.get(f"{FRONTEND_URL}/", timeout=30)
    assert r.status_code == 200, (
        f"GET {FRONTEND_URL}/ expected 200, got {r.status_code}: {r.text[:500]!r}"
    )
    body = r.text
    assert "VarTypeError" not in body, (
        "Rendered page body contains 'VarTypeError' — the ndarray serializer is not registered properly."
    )
    assert "Traceback (most recent call last)" not in body, (
        "Rendered page body contains a Python traceback — the backend errored while rendering."
    )


def test_regenerate_button_visible_on_page(reflex_app):
    r = requests.get(f"{FRONTEND_URL}/", timeout=30)
    assert r.status_code == 200, f"GET {FRONTEND_URL}/ failed with {r.status_code}"
    # Next.js dev mode inlines the compiled component source for the page; the
    # button label string should appear verbatim in the HTML.
    assert "Regenerate" in r.text, (
        "Could not find the 'Regenerate' button label in the rendered HTML at /."
    )


def test_points_endpoint_shape(reflex_app):
    r = requests.get(f"{BACKEND_URL}/api/points", timeout=15)
    assert r.status_code == 200, (
        f"GET {BACKEND_URL}/api/points expected 200, got {r.status_code}: {r.text[:500]!r}"
    )
    ctype = r.headers.get("content-type", "")
    assert ctype.lower().startswith("application/json"), (
        f"GET {BACKEND_URL}/api/points expected JSON content-type, got {ctype!r}"
    )

    data = r.json()
    assert isinstance(data, list), (
        f"GET {BACKEND_URL}/api/points expected a JSON array, got {type(data).__name__}: {data!r}"
    )
    assert len(data) == 50, (
        f"GET {BACKEND_URL}/api/points expected exactly 50 elements, got {len(data)}."
    )
    for i, item in enumerate(data):
        assert isinstance(item, dict), (
            f"Element {i} of /api/points response is not an object: {item!r}"
        )
        assert sorted(item.keys()) == ["x", "y"], (
            f"Element {i} must have exactly keys 'x' and 'y', got {sorted(item.keys())}."
        )
        for k in ("x", "y"):
            v = item[k]
            assert isinstance(v, (int, float)) and not isinstance(v, bool), (
                f"Element {i} key {k!r} must be a JSON number, got {type(v).__name__}: {v!r}"
            )
            # Make sure float(v) does not raise.
            float(v)


def test_points_endpoint_regenerates_fresh_data(reflex_app):
    r1 = requests.get(f"{BACKEND_URL}/api/points", timeout=15)
    time.sleep(0.2)
    r2 = requests.get(f"{BACKEND_URL}/api/points", timeout=15)

    assert r1.status_code == 200 and r2.status_code == 200, (
        f"Both calls to /api/points must succeed (got {r1.status_code} and {r2.status_code})."
    )
    a = r1.json()
    b = r2.json()
    assert isinstance(a, list) and isinstance(b, list), (
        "Both /api/points responses must be JSON arrays."
    )
    assert len(a) == 50 and len(b) == 50, (
        f"Both /api/points responses must have 50 items (got {len(a)} and {len(b)})."
    )

    differences = 0
    for ea, eb in zip(a, b):
        try:
            if abs(float(ea["y"]) - float(eb["y"])) > 1e-9:
                differences += 1
            if abs(float(ea["x"]) - float(eb["x"])) > 1e-9:
                differences += 1
        except (KeyError, TypeError, ValueError):
            differences += 1
    assert differences > 0, (
        "Two consecutive calls to /api/points returned identical data — the regeneration must produce fresh random samples."
    )
