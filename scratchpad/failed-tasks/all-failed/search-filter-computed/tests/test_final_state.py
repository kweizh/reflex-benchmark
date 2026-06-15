import ast
import glob
import os
import re
import signal
import socket
import subprocess
import time
from urllib.request import urlopen, Request
from urllib.error import URLError

import pytest


PROJECT_DIR = "/home/user/myproject"
APP_PACKAGE_DIR = os.path.join(PROJECT_DIR, "myproject")
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
START_TIMEOUT = 300  # cold-start Next.js build can be slow.


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _iter_app_source_modules():
    """Yield ast.Module trees for every .py file inside the Reflex app package."""
    pattern = os.path.join(APP_PACKAGE_DIR, "**", "*.py")
    for path in glob.glob(pattern, recursive=True):
        with open(path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=path)
            except SyntaxError as exc:  # pragma: no cover - surfaced via test failure
                pytest.fail(f"Failed to parse {path}: {exc}")
        yield path, tree


def _is_rx_state_base(base: ast.expr) -> bool:
    """Return True if `base` references `rx.State` / `reflex.State` / `State`."""
    if isinstance(base, ast.Attribute) and base.attr == "State":
        if isinstance(base.value, ast.Name) and base.value.id in {"rx", "reflex"}:
            return True
    if isinstance(base, ast.Name) and base.id == "State":
        return True
    return False


def _iter_state_classes():
    for path, tree in _iter_app_source_modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                _is_rx_state_base(b) for b in node.bases
            ):
                yield path, node


def _decorator_is_cached_var(dec: ast.expr) -> bool:
    """Return True if the decorator is `@rx.var(cache=True)` (or reflex.var)."""
    if not isinstance(dec, ast.Call):
        return False
    func = dec.func
    if isinstance(func, ast.Attribute) and func.attr == "var":
        if isinstance(func.value, ast.Name) and func.value.id in {"rx", "reflex"}:
            pass
        else:
            return False
    elif isinstance(func, ast.Name) and func.id == "var":
        pass
    else:
        return False
    for kw in dec.keywords:
        if kw.arg == "cache" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _class_attr_value(cls: ast.ClassDef, name: str):
    """Return the AST value of the class-level assignment to `name`, or None."""
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name:
            return stmt.value, stmt
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return stmt.value, stmt
    return None, None


def _find_method(cls: ast.ClassDef, name: str):
    for stmt in cls.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == name:
            return stmt
    return None


# ---------------------------------------------------------------------------
# Server fixture
# ---------------------------------------------------------------------------


def _port_is_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_status(url: str, timeout: float = 5.0):
    try:
        req = Request(url, headers={"User-Agent": "harbor-verifier/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except URLError:
        return None, b""
    except Exception:
        return None, b""


@pytest.fixture(scope="session")
def reflex_server():
    # Make sure no stale process is bound to our ports.
    subprocess.run(["pkill", "-f", "reflex run"], check=False)
    subprocess.run(["pkill", "-f", "next-server"], check=False)
    subprocess.run(["pkill", "-f", "uvicorn"], check=False)
    time.sleep(2)

    log_path = "/tmp/reflex_verifier.log"
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env={**os.environ},
        preexec_fn=os.setsid,
    )

    deadline = time.time() + START_TIMEOUT
    frontend_up = backend_up = False
    while time.time() < deadline:
        if proc.poll() is not None:
            log_file.flush()
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                tail = f.read()[-4000:]
            pytest.fail(
                "`uv run reflex run` exited prematurely with code "
                f"{proc.returncode}. Last log lines:\n{tail}"
            )
        frontend_up = frontend_up or _port_is_open("127.0.0.1", FRONTEND_PORT)
        backend_up = backend_up or _port_is_open("127.0.0.1", BACKEND_PORT)
        if frontend_up and backend_up:
            # Give Next.js a few extra seconds to finish its first render.
            time.sleep(5)
            break
        time.sleep(2)
    else:
        log_file.flush()
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            tail = f.read()[-4000:]
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        pytest.fail(
            "Reflex server did not become ready within "
            f"{START_TIMEOUT}s (frontend_up={frontend_up}, backend_up={backend_up}).\n"
            f"Log tail:\n{tail}"
        )

    yield proc

    # Teardown — kill the whole process group so Next.js subprocesses die too.
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    log_file.close()
    # Best-effort cleanup for any orphans the executor may have spawned.
    subprocess.run(["pkill", "-f", "reflex run"], check=False)
    subprocess.run(["pkill", "-f", "next-server"], check=False)
    subprocess.run(["pkill", "-f", "uvicorn"], check=False)


# ---------------------------------------------------------------------------
# AST tests
# ---------------------------------------------------------------------------


def test_state_class_exists():
    classes = list(_iter_state_classes())
    assert classes, (
        "Could not find any class that subclasses rx.State (or reflex.State) "
        f"in {APP_PACKAGE_DIR}."
    )


def test_state_declares_query_var():
    found = False
    for _, cls in _iter_state_classes():
        for stmt in cls.body:
            if (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == "query"
                and isinstance(stmt.annotation, ast.Name)
                and stmt.annotation.id == "str"
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value == ""
            ):
                found = True
                break
        if found:
            break
    assert found, (
        "Expected a State class with a class-level annotation `query: str = \"\"`."
    )


def test_state_declares_products_with_min_entries():
    matched_class = None
    for _, cls in _iter_state_classes():
        value, _ = _class_attr_value(cls, "products")
        if value is None:
            continue
        if not isinstance(value, ast.List):
            continue
        if len(value.elts) < 10:
            continue
        ok = True
        for elt in value.elts:
            if not isinstance(elt, ast.Dict):
                ok = False
                break
            keys = []
            for k in elt.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.append(k.value)
            if "name" not in keys or "category" not in keys:
                ok = False
                break
        if ok:
            matched_class = cls
            break
    assert matched_class is not None, (
        "Expected a State class with a `products` class attribute set to a list "
        "literal of at least 10 dict entries, each containing string keys "
        "`name` and `category`."
    )


def test_filtered_products_is_cached_computed_var():
    for _, cls in _iter_state_classes():
        method = _find_method(cls, "filtered_products")
        if method is None:
            continue
        if any(_decorator_is_cached_var(d) for d in method.decorator_list):
            return
    pytest.fail(
        "Expected the State class to define a `filtered_products` method decorated "
        "with `@rx.var(cache=True)`."
    )


def test_result_count_is_cached_computed_var():
    for _, cls in _iter_state_classes():
        method = _find_method(cls, "result_count")
        if method is None:
            continue
        if any(_decorator_is_cached_var(d) for d in method.decorator_list):
            return
    pytest.fail(
        "Expected the State class to define a `result_count` method decorated "
        "with `@rx.var(cache=True)`."
    )


def test_result_count_uses_len_of_filtered_products():
    for _, cls in _iter_state_classes():
        method = _find_method(cls, "result_count")
        if method is None:
            continue
        for node in ast.walk(method):
            if not isinstance(node, ast.Return) or node.value is None:
                continue
            call = node.value
            if not isinstance(call, ast.Call):
                continue
            if not (isinstance(call.func, ast.Name) and call.func.id == "len"):
                continue
            if len(call.args) != 1:
                continue
            arg = call.args[0]
            if (
                isinstance(arg, ast.Attribute)
                and arg.attr == "filtered_products"
                and isinstance(arg.value, ast.Name)
                and arg.value.id == "self"
            ):
                return
    pytest.fail(
        "Expected `result_count` to contain `return len(self.filtered_products)`."
    )


# ---------------------------------------------------------------------------
# Runtime tests
# ---------------------------------------------------------------------------


def test_frontend_reachable(reflex_server):
    status, _ = _http_status(f"http://localhost:{FRONTEND_PORT}/", timeout=15.0)
    assert status == 200, (
        f"Expected GET http://localhost:{FRONTEND_PORT}/ to return 200, got {status}."
    )


def test_backend_reachable(reflex_server):
    # Reflex backend exposes a /ping liveness endpoint.
    status, body = _http_status(f"http://localhost:{BACKEND_PORT}/ping", timeout=15.0)
    assert status == 200, (
        f"Expected GET http://localhost:{BACKEND_PORT}/ping to return 200, got {status}."
    )


def test_compiled_frontend_references_state_vars(reflex_server):
    status, body = _http_status(f"http://localhost:{FRONTEND_PORT}/", timeout=15.0)
    assert status == 200, (
        f"Expected GET http://localhost:{FRONTEND_PORT}/ to return 200, got {status}."
    )
    html = body.decode("utf-8", errors="replace")

    # Reflex compiles state field names verbatim into the static bundle.
    # We pull every /_next/static asset referenced by the page and concatenate
    # their bodies so the regex check below works against the entire bundle.
    asset_urls = set(re.findall(r"/_next/static/[^\"'>\s]+", html))
    combined = html
    for path in asset_urls:
        # Skip obviously non-text assets.
        if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".woff", ".woff2", ".ttf", ".otf", ".ico")):
            continue
        url = f"http://localhost:{FRONTEND_PORT}{path}"
        s, b = _http_status(url, timeout=15.0)
        if s == 200:
            combined += "\n" + b.decode("utf-8", errors="replace")

    for needle in ("query", "filtered_products", "result_count"):
        assert needle in combined, (
            f"Expected the compiled frontend bundle to contain a reference to "
            f"`{needle}`, but it was not found across the HTML and /_next/static "
            f"assets fetched from http://localhost:{FRONTEND_PORT}/."
        )
