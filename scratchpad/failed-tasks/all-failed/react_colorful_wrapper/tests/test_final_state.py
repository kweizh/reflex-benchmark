import ast
import os
import re
import shutil
import socket
import subprocess
import time
from typing import Iterable, List, Optional, Tuple

import pytest


PROJECT_DIR = "/home/user/myproject"
EXPORT_TIMEOUT = 600
RUN_READINESS_TIMEOUT = 300
FRONTEND_PORT = 3000
BACKEND_PORT = 8000


# ---------------------------------------------------------------------------
# Helpers for source discovery and AST analysis
# ---------------------------------------------------------------------------


SKIP_DIRS = {".venv", "venv", "__pycache__", ".web", "node_modules", ".git", "dist", "build"}


def _iter_project_python_files(root: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _parse(path: str) -> Optional[ast.Module]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        return ast.parse(src, filename=path)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def _is_no_ssr_base(base: ast.expr) -> bool:
    """Return True if `base` looks like NoSSRComponent (possibly via alias)."""
    if isinstance(base, ast.Name):
        return base.id.endswith("NoSSRComponent")
    if isinstance(base, ast.Attribute):
        return base.attr.endswith("NoSSRComponent")
    return False


def _is_rx_state_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Attribute):
        return base.attr == "State" and isinstance(base.value, ast.Name) and base.value.id in {"rx", "reflex"}
    if isinstance(base, ast.Name):
        return base.id == "State"
    return False


def _str_value(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_class_attr(class_node: ast.ClassDef, name: str) -> Optional[ast.expr]:
    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name:
            if stmt.value is not None:
                return stmt.value
    return None


def _extract_annotation(class_node: ast.ClassDef, name: str) -> Optional[ast.expr]:
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name:
            return stmt.annotation
    return None


def _annotation_contains(annotation: ast.expr, *needles: str) -> bool:
    src = ast.unparse(annotation)
    return all(needle in src for needle in needles)


def _find_no_ssr_component_classes() -> List[Tuple[str, ast.ClassDef]]:
    matches: List[Tuple[str, ast.ClassDef]] = []
    for py_file in _iter_project_python_files(PROJECT_DIR):
        tree = _parse(py_file)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(_is_no_ssr_base(b) for b in node.bases):
                matches.append((py_file, node))
    return matches


def _find_state_classes() -> List[Tuple[str, ast.ClassDef]]:
    matches: List[Tuple[str, ast.ClassDef]] = []
    for py_file in _iter_project_python_files(PROJECT_DIR):
        tree = _parse(py_file)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(_is_rx_state_base(b) for b in node.bases):
                matches.append((py_file, node))
    return matches


# ---------------------------------------------------------------------------
# Process / port helpers
# ---------------------------------------------------------------------------


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _kill_reflex_processes() -> None:
    for pattern in ["reflex run", "next-server", "node .*next", "next dev", "uv run reflex"]:
        subprocess.run(["pkill", "-f", pattern], capture_output=True)
    # Give the OS a moment to release the ports.
    time.sleep(2)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_clean_processes():
    _kill_reflex_processes()
    yield
    _kill_reflex_processes()


# ---------------------------------------------------------------------------
# 1. Project layout
# ---------------------------------------------------------------------------


def test_project_directory_present():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_pyproject_lists_reflex():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), f"{pyproject} missing."
    with open(pyproject, "r", encoding="utf-8") as f:
        content = f.read().lower()
    assert "reflex" in content, "pyproject.toml does not declare a reflex dependency."


# ---------------------------------------------------------------------------
# 2. Custom component static checks
# ---------------------------------------------------------------------------


def test_no_ssr_component_subclass_exists():
    matches = _find_no_ssr_component_classes()
    assert matches, (
        "Could not find any class subclassing NoSSRComponent under "
        f"{PROJECT_DIR}; the wrapper must subclass reflex.components.component.NoSSRComponent."
    )


def test_component_library_attribute_is_react_colorful():
    matches = _find_no_ssr_component_classes()
    assert matches, "No NoSSRComponent subclass found."
    library_pattern = re.compile(r"^react-colorful(@[^\"' ]+)?$")
    valid = []
    for path, cls in matches:
        node = _extract_class_attr(cls, "library")
        if node is None:
            continue
        value = _str_value(node)
        if value is not None and library_pattern.match(value):
            valid.append((path, cls.name, value))
    assert valid, (
        "No NoSSRComponent subclass declares `library = 'react-colorful'` "
        "(optionally with an @version suffix)."
    )


def test_component_tag_attribute_is_hex_color_picker():
    matches = _find_no_ssr_component_classes()
    assert matches, "No NoSSRComponent subclass found."
    valid = []
    for path, cls in matches:
        tag_node = _extract_class_attr(cls, "tag")
        if tag_node is None:
            continue
        value = _str_value(tag_node)
        if value == "HexColorPicker":
            valid.append((path, cls.name))
    assert valid, "No NoSSRComponent subclass declares `tag = 'HexColorPicker'`."


def _color_picker_classes() -> List[Tuple[str, ast.ClassDef]]:
    result: List[Tuple[str, ast.ClassDef]] = []
    library_pattern = re.compile(r"^react-colorful(@[^\"' ]+)?$")
    for path, cls in _find_no_ssr_component_classes():
        lib_node = _extract_class_attr(cls, "library")
        tag_node = _extract_class_attr(cls, "tag")
        lib_value = _str_value(lib_node) if lib_node is not None else None
        tag_value = _str_value(tag_node) if tag_node is not None else None
        if lib_value and library_pattern.match(lib_value) and tag_value == "HexColorPicker":
            result.append((path, cls))
    return result


def test_component_color_prop_annotation():
    candidates = _color_picker_classes()
    assert candidates, "No HexColorPicker wrapper class found."
    for _, cls in candidates:
        ann = _extract_annotation(cls, "color")
        if ann is not None and _annotation_contains(ann, "Var", "str"):
            return
    pytest.fail(
        "The wrapper component must declare an annotated prop "
        "`color: rx.Var[str]` (or reflex.Var[str])."
    )


def test_component_on_change_event_handler():
    candidates = _color_picker_classes()
    assert candidates, "No HexColorPicker wrapper class found."
    for _, cls in candidates:
        ann = _extract_annotation(cls, "on_change")
        if ann is None:
            continue
        if "EventHandler" not in ast.unparse(ann):
            continue
        # Look for the lambda inside the annotation subscript.
        lambda_nodes = [n for n in ast.walk(ann) if isinstance(n, ast.Lambda)]
        if not lambda_nodes:
            continue
        for lam in lambda_nodes:
            args = lam.args
            positional = args.args + args.posonlyargs
            if len(positional) != 1:
                continue
            arg_name = positional[0].arg
            body = lam.body
            if isinstance(body, ast.List) and len(body.elts) == 1:
                element = body.elts[0]
                if isinstance(element, ast.Name) and element.id == arg_name:
                    return
    pytest.fail(
        "The wrapper component must declare `on_change` as an "
        "`rx.EventHandler[lambda color: [color]]` (single-arg lambda that "
        "returns a list of that arg)."
    )


# ---------------------------------------------------------------------------
# 3. State and page wiring
# ---------------------------------------------------------------------------


def _state_string_var(cls: ast.ClassDef) -> Optional[str]:
    """Return the name of an annotated string-typed class attribute."""
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            ann_src = ast.unparse(stmt.annotation)
            if ann_src.strip() == "str":
                return stmt.target.id
    return None


def _state_event_handler_for(cls: ast.ClassDef, var_name: str) -> Optional[ast.FunctionDef]:
    for stmt in cls.body:
        if isinstance(stmt, ast.FunctionDef):
            args = stmt.args
            positional = args.posonlyargs + args.args
            if len(positional) != 2:
                continue  # self + one parameter
            # Look for an assignment `self.<var_name> = <param>`
            for sub in ast.walk(stmt):
                if (
                    isinstance(sub, ast.Assign)
                    and len(sub.targets) == 1
                    and isinstance(sub.targets[0], ast.Attribute)
                    and isinstance(sub.targets[0].value, ast.Name)
                    and sub.targets[0].value.id == "self"
                    and sub.targets[0].attr == var_name
                ):
                    return stmt
    return None


def test_state_holds_hex_color_string():
    state_classes = _find_state_classes()
    assert state_classes, "No subclass of rx.State found in the project."
    for _, cls in state_classes:
        var_name = _state_string_var(cls)
        if var_name is None:
            continue
        handler = _state_event_handler_for(cls, var_name)
        if handler is not None:
            return
    pytest.fail(
        "Could not find an rx.State subclass that declares a string-typed state "
        "var AND an event handler taking a single argument that assigns it to that var."
    )


def test_index_page_uses_wrapped_component_and_text():
    """The index page must mention the wrapped component AND an rx.text with background_color bound to the state hex color."""
    candidates = _color_picker_classes()
    assert candidates, "Wrapper class missing."
    wrapper_names = {cls.name for _, cls in candidates}

    state_classes = _find_state_classes()
    state_var_pairs: List[Tuple[str, str]] = []
    for _, cls in state_classes:
        var_name = _state_string_var(cls)
        if var_name is not None:
            state_var_pairs.append((cls.name, var_name))
    assert state_var_pairs, "No state with a string var was found."

    # Inspect each python file looking for a call that references the wrapper
    # AND an rx.text call whose background_color kwarg references the state var.
    found = False
    text_pattern = re.compile(r"\b(?:rx|reflex)\.text\b")
    for py_file in _iter_project_python_files(PROJECT_DIR):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError:
            continue
        if not any(name in source for name in wrapper_names) and not any(
            f"{name.lower()}(" in source for name in wrapper_names
        ):
            # Component might be exposed via a constructor variable; keep checking.
            pass
        try:
            tree = ast.parse(source, filename=py_file)
        except SyntaxError:
            continue

        text_calls_ok = False
        wrapper_referenced = any(name in source for name in wrapper_names)
        # Also accept references through `.create` constructor variables: heuristic
        # by simply searching for any wrapper class name appearance OR a lower-cased
        # alias defined in the same file.
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_src = ast.unparse(node.func)
                if text_pattern.search(func_src):
                    for kw in node.keywords:
                        if kw.arg == "background_color":
                            value_src = ast.unparse(kw.value)
                            for state_cls_name, var_name in state_var_pairs:
                                if (
                                    f"{state_cls_name}.{var_name}" in value_src
                                    or f".{var_name}" in value_src
                                ):
                                    text_calls_ok = True
                                    break
                        if text_calls_ok:
                            break
            if text_calls_ok:
                break

        if wrapper_referenced and text_calls_ok:
            found = True
            break

    assert found, (
        "Could not find a page module that simultaneously renders the wrapped "
        "color picker component AND an rx.text(...) call with background_color "
        "bound to the state hex color var."
    )


# ---------------------------------------------------------------------------
# 4. Frontend bundle includes react-colorful
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def reflex_export():
    static_dir = os.path.join(PROJECT_DIR, ".web", "_static")
    if os.path.isdir(static_dir):
        shutil.rmtree(static_dir, ignore_errors=True)
    result = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=EXPORT_TIMEOUT,
    )
    return result


def test_reflex_export_exits_zero(reflex_export):
    assert reflex_export.returncode == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed.\n"
        f"stdout:\n{reflex_export.stdout}\n\nstderr:\n{reflex_export.stderr}"
    )


def test_static_directory_exists(reflex_export):
    static_dir = os.path.join(PROJECT_DIR, ".web", "_static")
    assert os.path.isdir(static_dir), (
        f"Expected exported static assets at {static_dir} after running reflex export."
    )
    has_files = False
    for _, _, files in os.walk(static_dir):
        if files:
            has_files = True
            break
    assert has_files, f"{static_dir} exists but is empty."


def test_bundle_references_react_colorful(reflex_export):
    static_dir = os.path.join(PROJECT_DIR, ".web", "_static")
    assert os.path.isdir(static_dir), f"{static_dir} missing."
    needle = b"react-colorful"
    for dirpath, _, files in os.walk(static_dir):
        for name in files:
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as f:
                    if needle in f.read():
                        return
            except OSError:
                continue
    pytest.fail(
        f"No file under {static_dir} contains the substring 'react-colorful'; "
        "the compiled frontend does not appear to bundle the npm package."
    )


# ---------------------------------------------------------------------------
# 5. App runs and serves the index page
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def running_reflex_app():
    _kill_reflex_processes()
    log_path = "/tmp/reflex_run.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run", "--env", "dev", "--loglevel", "info"],
        cwd=PROJECT_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    ready = False
    deadline = time.time() + RUN_READINESS_TIMEOUT
    while time.time() < deadline:
        if _port_open("127.0.0.1", FRONTEND_PORT):
            ready = True
            break
        if proc.poll() is not None:
            break
        time.sleep(2)

    yield {"proc": proc, "ready": ready, "log": log_path}

    try:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    finally:
        log_file.close()
        _kill_reflex_processes()


def test_reflex_app_starts_and_serves_index(running_reflex_app):
    assert running_reflex_app["ready"], (
        "Reflex dev server did not start listening on port 3000 within the timeout. "
        f"See log at {running_reflex_app['log']} for details."
    )

    # Hit the index route with the stdlib so we don't need extra dependencies.
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:3000/", timeout=30) as response:
            status = response.status
            body = response.read()
    except urllib.error.URLError as exc:
        pytest.fail(f"Could not connect to http://127.0.0.1:3000/: {exc}")
        return

    assert status == 200, f"Expected HTTP 200 from index, got {status}."
    assert body, "Index page returned an empty body."


def test_no_lingering_reflex_processes(running_reflex_app):
    """After the running_reflex_app fixture tears down, no reflex servers should remain."""
    # The fixture teardown happens at session end; here we only confirm that
    # the fixture itself did not leave the server bound after we explicitly
    # asked for cleanup at the end of the test session.
    # We additionally force kill and check the ports are free.
    _kill_reflex_processes()
    time.sleep(2)
    assert not _port_open("127.0.0.1", FRONTEND_PORT, timeout=1.0), (
        f"Port {FRONTEND_PORT} is still bound after cleanup; a Reflex server is still running."
    )
    assert not _port_open("127.0.0.1", BACKEND_PORT, timeout=1.0), (
        f"Port {BACKEND_PORT} is still bound after cleanup; a Reflex backend is still running."
    )
