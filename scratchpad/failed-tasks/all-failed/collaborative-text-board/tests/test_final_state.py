import ast
import glob
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest


PROJECT_DIR = "/home/user/collab_board"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000

REFLEX_LOG = "/tmp/reflex_final.log"
REFLEX_PIDFILE = "/tmp/reflex_final.pid"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_state_modules() -> list[str]:
    """Find candidate Python files that may define the Reflex state.

    Reflex's blank template places the main module at
    `<project>/collab_board/collab_board.py`. We also search for a sibling
    `state.py` for flexibility.
    """
    candidates: list[str] = []
    for pattern in (
        os.path.join(PROJECT_DIR, "collab_board", "*.py"),
        os.path.join(PROJECT_DIR, "**", "*.py"),
    ):
        for path in glob.glob(pattern, recursive=True):
            # Skip generated / vendored files.
            if "/.web/" in path or "/.venv/" in path or "/__pycache__/" in path:
                continue
            if os.path.basename(path).startswith("test_"):
                continue
            candidates.append(path)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _parse(path: str) -> ast.Module:
    with open(path, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=path)


def _module_level_global_feed(tree: ast.Module) -> tuple[str, ast.AST] | None:
    """Return (name, assignment_node) for a module-level GLOBAL_FEED list, or None."""
    for node in tree.body:
        # Annotated assignment: `_GLOBAL_FEED: list[dict] = []`
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if name in ("_GLOBAL_FEED", "GLOBAL_FEED"):
                return name, node
        # Plain assignment: `_GLOBAL_FEED = []`
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in ("_GLOBAL_FEED", "GLOBAL_FEED"):
                    return tgt.id, node
    return None


def _iter_classdefs(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            yield node


def _is_rx_event_background(decorator: ast.expr) -> bool:
    """Return True if the decorator is exactly `@rx.event(background=True)`."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    # rx.event(...)
    if isinstance(func, ast.Attribute) and func.attr == "event":
        if isinstance(func.value, ast.Name) and func.value.id in ("rx", "reflex"):
            for kw in decorator.keywords:
                if kw.arg == "background" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value is True:
                    return True
    return False


def _walk_calls(node: ast.AST):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            yield sub


def _has_async_with_self(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.AsyncWith):
            for item in sub.items:
                expr = item.context_expr
                if isinstance(expr, ast.Name) and expr.id == "self":
                    return True
    return False


def _has_asyncio_sleep_call(node: ast.AST) -> bool:
    for call in _walk_calls(node):
        func = call.func
        if isinstance(func, ast.Attribute) and func.attr == "sleep":
            if isinstance(func.value, ast.Name) and func.value.id == "asyncio":
                return True
    return False


def _references_self_stopped(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "_stopped":
            if isinstance(sub.value, ast.Name) and sub.value.id == "self":
                return True
    return False


def _appends_to_global_feed(node: ast.AST, feed_names: set[str]) -> bool:
    for call in _walk_calls(node):
        func = call.func
        if isinstance(func, ast.Attribute) and func.attr == "append":
            if isinstance(func.value, ast.Name) and func.value.id in feed_names:
                return True
    return False


def _state_class_fields(cls: ast.ClassDef) -> dict[str, str]:
    """Return {field_name: annotation_str} for AnnAssigns directly on the class body."""
    out: dict[str, str] = {}
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            try:
                ann_src = ast.unparse(stmt.annotation)
            except Exception:
                ann_src = ""
            out[stmt.target.id] = ann_src
    return out


def _find_background_methods(cls: ast.ClassDef):
    for stmt in cls.body:
        if isinstance(stmt, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for dec in stmt.decorator_list:
                if _is_rx_event_background(dec):
                    yield stmt
                    break


def _find_method(cls: ast.ClassDef, name: str):
    for stmt in cls.body:
        if isinstance(stmt, (ast.AsyncFunctionDef, ast.FunctionDef)) and stmt.name == name:
            return stmt
    return None


def _state_module_and_class() -> tuple[str, ast.Module, ast.ClassDef, str]:
    """Locate the state module: a file with a module-level GLOBAL_FEED list and a
    class deriving (directly) from `rx.State`. Returns (path, tree, class, feed_name).
    """
    errors: list[str] = []
    for path in _find_state_modules():
        try:
            tree = _parse(path)
        except SyntaxError as e:
            errors.append(f"{path}: syntax error {e}")
            continue
        gf = _module_level_global_feed(tree)
        if gf is None:
            continue
        for cls in _iter_classdefs(tree):
            for base in cls.bases:
                base_src = ""
                try:
                    base_src = ast.unparse(base)
                except Exception:
                    pass
                if base_src in ("rx.State", "reflex.State"):
                    return path, tree, cls, gf[0]
    pytest.fail(
        "Could not locate a state module containing both a module-level "
        "`_GLOBAL_FEED` (or `GLOBAL_FEED`) list and a class deriving from rx.State. "
        f"Inspected files: {errors or _find_state_modules()}"
    )


def _wait_for_port(host: str, port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(1.0)
    return False


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if hasattr(e, "read") else b""


# ---------------------------------------------------------------------------
# Reflex server fixture (subprocess + uv)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def reflex_server():
    # Always kill any previously running reflex processes to keep teardown safe.
    subprocess.run(["pkill", "-f", "reflex run"], check=False)
    subprocess.run(["pkill", "-f", "reflex.app"], check=False)
    time.sleep(1.0)

    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} must exist."
    assert shutil.which("uv") is not None, "uv must be installed for the verifier."

    log = open(REFLEX_LOG, "w")
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=log,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        start_new_session=True,
    )
    with open(REFLEX_PIDFILE, "w") as pf:
        pf.write(str(proc.pid))

    backend_ready = _wait_for_port("127.0.0.1", BACKEND_PORT, timeout=180.0)
    frontend_ready = _wait_for_port("127.0.0.1", FRONTEND_PORT, timeout=180.0)

    yield {
        "proc": proc,
        "backend_ready": backend_ready,
        "frontend_ready": frontend_ready,
    }

    # ---- Teardown: ALWAYS kill the background server. ----
    try:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass
    subprocess.run(["pkill", "-f", "reflex run"], check=False)
    subprocess.run(["pkill", "-f", "reflex.app"], check=False)
    try:
        log.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# AST tests (run without starting the server)
# ---------------------------------------------------------------------------


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected the executor to create the Reflex project at {PROJECT_DIR}."
    )
    assert os.path.isfile(os.path.join(PROJECT_DIR, "pyproject.toml")), (
        "Expected pyproject.toml at the project root (created by `uv init`)."
    )
    assert os.path.isfile(os.path.join(PROJECT_DIR, "rxconfig.py")), (
        "Expected rxconfig.py at the project root (created by `reflex init`)."
    )


def test_module_level_global_feed_is_a_list():
    path, tree, _cls, feed_name = _state_module_and_class()
    gf = _module_level_global_feed(tree)
    assert gf is not None, (
        f"State module {path} must declare a module-level _GLOBAL_FEED / GLOBAL_FEED."
    )
    name, node = gf
    # Value should be a list literal (or `list(...)` ctor call).
    if isinstance(node, ast.AnnAssign):
        value = node.value
    elif isinstance(node, ast.Assign):
        value = node.value
    else:
        value = None
    is_list = isinstance(value, ast.List) or (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "list"
    )
    assert is_list, (
        f"Module-level `{name}` in {path} must be initialized as a list "
        "(e.g. `_GLOBAL_FEED: list[dict] = []`)."
    )


def test_state_class_has_required_vars():
    path, _tree, cls, _feed_name = _state_module_and_class()
    fields = _state_class_fields(cls)
    for required in ("feed", "username", "draft", "_stopped"):
        assert required in fields, (
            f"State class {cls.name} in {path} is missing required field "
            f"`{required}`. Found fields: {list(fields)}."
        )
    # feed must be a list, username a str, draft a str, _stopped a bool.
    assert "list" in fields["feed"], (
        f"`feed` must be typed as a list (got `{fields['feed']}`)."
    )
    assert "str" in fields["username"], (
        f"`username` must be typed as str (got `{fields['username']}`)."
    )
    assert "str" in fields["draft"], (
        f"`draft` must be typed as str (got `{fields['draft']}`)."
    )
    assert "bool" in fields["_stopped"], (
        f"`_stopped` must be typed as bool (got `{fields['_stopped']}`)."
    )
    # _stopped must start with an underscore (backend-only).
    assert "_stopped" in fields and fields["_stopped"], (
        "`_stopped` must be a backend-only var (single-underscore prefix)."
    )


def test_background_poll_event_exists():
    path, _tree, cls, _feed_name = _state_module_and_class()
    bg_methods = list(_find_background_methods(cls))
    assert bg_methods, (
        f"State class {cls.name} in {path} must contain a method decorated with "
        "`@rx.event(background=True)`."
    )
    # At least one background method must use `async with self:` AND asyncio.sleep
    # AND reference self._stopped.
    ok = False
    for m in bg_methods:
        if (
            isinstance(m, ast.AsyncFunctionDef)
            and _has_async_with_self(m)
            and _has_asyncio_sleep_call(m)
            and _references_self_stopped(m)
        ):
            ok = True
            break
    assert ok, (
        "A background event handler must (1) be async, (2) contain an "
        "`async with self:` block, (3) call `asyncio.sleep(...)`, and "
        "(4) reference `self._stopped` to control the loop."
    )


def test_send_message_mutates_global_feed():
    path, _tree, cls, feed_name = _state_module_and_class()
    method = _find_method(cls, "send_message")
    assert method is not None, (
        f"State class {cls.name} in {path} must define a `send_message` method."
    )
    # send_message must NOT be a background event handler.
    for dec in method.decorator_list:
        assert not _is_rx_event_background(dec), (
            "`send_message` must be a standard (non-background) event handler."
        )
    assert _appends_to_global_feed(method, {feed_name}), (
        f"`send_message` must mutate the module-level `{feed_name}` list "
        f"(e.g. `{feed_name}.append({{...}})`)."
    )


def test_page_registers_on_load_polling():
    """The page at `/` must register on_load that triggers the polling task."""
    path, tree, cls, _feed_name = _state_module_and_class()
    # Collect names of all @rx.event(background=True) methods on the state class.
    bg_names = {m.name for m in _find_background_methods(cls)}
    assert bg_names, "Expected at least one background event method on the state class."

    # Search every .py file under the project for either:
    #   @rx.page(... on_load=<...>)
    # or
    #   app.add_page(... on_load=<...>)
    # where <...> references one of the bg_names.
    found = False
    for fp in _find_state_modules():
        try:
            ft = _parse(fp)
        except SyntaxError:
            continue
        for node in ast.walk(ft):
            if not isinstance(node, ast.Call):
                continue
            on_load_val: ast.expr | None = None
            # @rx.page(on_load=...)
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("page", "add_page"):
                for kw in node.keywords:
                    if kw.arg == "on_load":
                        on_load_val = kw.value
                        break
            if on_load_val is None:
                continue
            try:
                rendered = ast.unparse(on_load_val)
            except Exception:
                rendered = ""
            if any(name in rendered for name in bg_names):
                found = True
                break
        if found:
            break
    assert found, (
        "Could not find an `on_load=` registration (on `@rx.page` or "
        "`app.add_page`) that references the background polling task. "
        f"Background task names searched: {bg_names}."
    )


# ---------------------------------------------------------------------------
# Live server tests
# ---------------------------------------------------------------------------


def test_backend_is_listening(reflex_server):
    assert reflex_server["backend_ready"], (
        f"Reflex backend did not become ready on port {BACKEND_PORT}. "
        f"See {REFLEX_LOG}."
    )


def test_frontend_is_listening(reflex_server):
    assert reflex_server["frontend_ready"], (
        f"Reflex frontend did not become ready on port {FRONTEND_PORT}. "
        f"See {REFLEX_LOG}."
    )


def test_backend_ping(reflex_server):
    if not reflex_server["backend_ready"]:
        pytest.skip("backend not ready")
    status, body = _http_get(f"http://127.0.0.1:{BACKEND_PORT}/ping", timeout=10)
    assert status == 200, f"GET /ping returned status {status}"
    assert b"pong" in body, f"Expected 'pong' in /ping response, got: {body!r}"


def test_frontend_serves_index(reflex_server):
    if not reflex_server["frontend_ready"]:
        pytest.skip("frontend not ready")
    status, _ = _http_get(f"http://127.0.0.1:{FRONTEND_PORT}/", timeout=15)
    assert status == 200, f"GET / on frontend returned status {status}"


def test_compiled_frontend_contains_send_and_foreach(reflex_server):
    """Once the dev server has compiled, .web/pages/index.{js,jsx} should
    contain the literal label `Send` and a `.map(` call (which is how Reflex
    compiles `rx.foreach`).
    """
    if not reflex_server["frontend_ready"]:
        pytest.skip("frontend not ready; cannot inspect compiled output")
    web_dir = os.path.join(PROJECT_DIR, ".web", "pages")
    assert os.path.isdir(web_dir), (
        f"Expected compiled frontend directory {web_dir} to exist after the "
        "dev server has started."
    )
    deadline = time.time() + 90
    candidates: list[str] = []
    contents = ""
    while time.time() < deadline:
        candidates = (
            glob.glob(os.path.join(web_dir, "index.js"))
            + glob.glob(os.path.join(web_dir, "index.jsx"))
            + glob.glob(os.path.join(web_dir, "index", "*.js"))
            + glob.glob(os.path.join(web_dir, "index", "*.jsx"))
        )
        contents = ""
        for c in candidates:
            try:
                with open(c, "r", encoding="utf-8", errors="ignore") as f:
                    contents += "\n" + f.read()
            except OSError:
                continue
        if "Send" in contents and ".map(" in contents:
            break
        time.sleep(2)

    assert candidates, (
        f"No compiled index page found under {web_dir}. The frontend may not "
        "have finished compiling."
    )
    assert "Send" in contents, (
        "Compiled frontend does not contain the `Send` button label. "
        f"Files inspected: {candidates}"
    )
    assert ".map(" in contents, (
        "Compiled frontend does not contain a `.map(` call. `rx.foreach` is "
        "required to render the feed list reactively. "
        f"Files inspected: {candidates}"
    )
