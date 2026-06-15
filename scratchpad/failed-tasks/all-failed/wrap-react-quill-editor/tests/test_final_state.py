import ast
import json
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
APP_PKG_DIR = "/home/user/myproject/myproject"
WEB_PACKAGE_JSON = "/home/user/myproject/.web/package.json"
RXCONFIG_PATH = "/home/user/myproject/rxconfig.py"

FRONTEND_PORT = 3000
BACKEND_PORT = 8000


# ----------------------------- AST helpers --------------------------------- #

def _iter_py_files(root: str):
    for dirpath, _dirnames, filenames in os.walk(root):
        # skip vendor / build directories
        parts = set(Path(dirpath).parts)
        if any(p in parts for p in {".web", "__pycache__", ".venv", "node_modules", ".states"}):
            continue
        for fname in filenames:
            if fname.endswith(".py"):
                yield os.path.join(dirpath, fname)


def _parse_files(root: str):
    trees = []
    for p in _iter_py_files(root):
        try:
            with open(p, "r", encoding="utf-8") as f:
                source = f.read()
            trees.append((p, ast.parse(source), source))
        except (SyntaxError, UnicodeDecodeError):
            continue
    return trees


def _base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    if isinstance(base, ast.Subscript):
        return _base_name(base.value)
    return ""


def _annotation_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _find_react_quill_class():
    for path, tree, _src in _parse_files(APP_PKG_DIR):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ReactQuill":
                bases = [_base_name(b) for b in node.bases]
                if any(b == "NoSSRComponent" for b in bases):
                    return path, node
    return None, None


def _find_state_class():
    """Return (path, ClassDef) of the first class inheriting from rx.State."""
    for path, tree, _src in _parse_files(APP_PKG_DIR):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for b in node.bases:
                    text = _annotation_text(b)
                    if text in {"rx.State", "reflex.State", "State"} and node.name != "State":
                        # heuristic: rx.State / reflex.State always; bare "State" inherit only if module imports reflex State
                        return path, node
                    if text in {"rx.State", "reflex.State"}:
                        return path, node
    return None, None


# ----------------------------- AST tests ----------------------------------- #

def test_react_quill_class_exists_and_subclasses_no_ssr():
    path, cls = _find_react_quill_class()
    assert cls is not None, (
        f"Could not find a class named `ReactQuill` inheriting from `NoSSRComponent` under {APP_PKG_DIR}."
    )
    assert path is not None


def test_react_quill_library_is_pinned():
    _path, cls = _find_react_quill_class()
    assert cls is not None, "ReactQuill class not found."
    library_value = None
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "library":
                    if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                        library_value = stmt.value.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "library":
            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                library_value = stmt.value.value
    assert library_value is not None, (
        "ReactQuill must declare a `library` string attribute (e.g., `library = 'react-quill@2.0.0'`)."
    )
    assert "react-quill" in library_value, (
        f"Expected `library` to reference 'react-quill', got: {library_value!r}."
    )
    assert "2.0.0" in library_value, (
        f"Expected `library` to pin version 2.0.0, got: {library_value!r}."
    )


def test_react_quill_tag_is_react_quill():
    _path, cls = _find_react_quill_class()
    assert cls is not None, "ReactQuill class not found."
    tag_value = None
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "tag":
                    if isinstance(stmt.value, ast.Constant):
                        tag_value = stmt.value.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "tag":
            if isinstance(stmt.value, ast.Constant):
                tag_value = stmt.value.value
    assert tag_value == "ReactQuill", (
        f"Expected `tag = 'ReactQuill'` in the ReactQuill class, got: {tag_value!r}."
    )


def test_react_quill_value_prop():
    _path, cls = _find_react_quill_class()
    assert cls is not None, "ReactQuill class not found."
    found = False
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "value":
            ann_text = _annotation_text(stmt.annotation)
            # Accept rx.Var[str] / reflex.Var[str] / Var[str]
            if re.search(r"\b(rx|reflex)?\.?Var\[\s*str\s*\]", ann_text):
                found = True
    assert found, (
        "ReactQuill must declare an annotated prop `value: rx.Var[str]`."
    )


def test_react_quill_on_change_event_handler():
    _path, cls = _find_react_quill_class()
    assert cls is not None, "ReactQuill class not found."
    found = False
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "on_change":
            ann_text = _annotation_text(stmt.annotation)
            if re.search(r"\b(rx|reflex)?\.?EventHandler\[", ann_text):
                found = True
    assert found, (
        "ReactQuill must declare an event handler `on_change: rx.EventHandler[...]`."
    )


def test_react_quill_factory_exported():
    """A module-level `react_quill = ReactQuill.create` must exist somewhere."""
    for _path, tree, _src in _parse_files(APP_PKG_DIR):
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name) and tgt.id == "react_quill":
                    val = node.value
                    if isinstance(val, ast.Attribute) and val.attr == "create":
                        if isinstance(val.value, ast.Name) and val.value.id == "ReactQuill":
                            return
    pytest.fail(
        "Expected a module-level assignment `react_quill = ReactQuill.create` exposed as a factory."
    )


# ----------------------------- State tests --------------------------------- #

def _iter_classes_inheriting_state():
    for path, tree, _src in _parse_files(APP_PKG_DIR):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for b in node.bases:
                    text = _annotation_text(b)
                    if text in {"rx.State", "reflex.State"}:
                        yield path, node


def test_state_has_content_str_field():
    found = False
    for _path, cls in _iter_classes_inheriting_state():
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "content":
                ann_text = _annotation_text(stmt.annotation)
                if ann_text == "str" and isinstance(stmt.value, ast.Constant) and stmt.value.value == "":
                    found = True
    assert found, (
        "Expected a class inheriting from `rx.State` to declare `content: str = \"\"`."
    )


def test_state_has_set_content_handler():
    found = False
    for _path, cls in _iter_classes_inheriting_state():
        # Need both content field and set_content handler in same class.
        has_content = False
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "content":
                has_content = True
        if not has_content:
            continue
        for stmt in cls.body:
            if isinstance(stmt, ast.FunctionDef) and stmt.name == "set_content":
                args = [a.arg for a in stmt.args.args]
                if args[:2] != ["self", "v"]:
                    continue
                # Body must assign self.content = v
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
                        tgt = sub.targets[0]
                        if (
                            isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "self"
                            and tgt.attr == "content"
                            and isinstance(sub.value, ast.Name)
                            and sub.value.id == "v"
                        ):
                            found = True
    assert found, (
        "Expected the state class to define `set_content(self, v: str)` that assigns `self.content = v`."
    )


# --------------------------- Stylesheet wiring ----------------------------- #

def test_quill_stylesheet_is_wired():
    """rxconfig stylesheets contains a `quill` URL, or ReactQuill declares lib_dependencies containing 'quill'."""
    # Path A: rxconfig stylesheets
    rx_ok = False
    if os.path.isfile(RXCONFIG_PATH):
        try:
            with open(RXCONFIG_PATH, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    elif isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    if func_name == "Config":
                        for kw in node.keywords:
                            if kw.arg == "stylesheets" and isinstance(kw.value, (ast.List, ast.Tuple)):
                                for elt in kw.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        if "quill" in elt.value.lower():
                                            rx_ok = True
        except SyntaxError:
            pass

    # Path B: ReactQuill.lib_dependencies references quill
    lib_dep_ok = False
    _path, cls = _find_react_quill_class()
    if cls is not None:
        for stmt in cls.body:
            target_name = None
            value = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                target_name = stmt.targets[0].id
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target_name = stmt.target.id
                value = stmt.value
            if target_name == "lib_dependencies" and isinstance(value, (ast.List, ast.Tuple)):
                for elt in value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        if "quill" in elt.value.lower():
                            lib_dep_ok = True

    assert rx_ok or lib_dep_ok, (
        "Expected Quill's stylesheet to be wired in either `rxconfig.py` (via `stylesheets=[...]` "
        "containing a 'quill' URL) or via `lib_dependencies` containing a 'quill' entry on the ReactQuill class."
    )


# -------------------------- .web/package.json ------------------------------ #

def _wait_for_port(host: str, port: int, timeout: float = 240.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(1.0)
    return False


def _run_reflex_export():
    """Make sure .web/package.json is regenerated by running `reflex export --frontend-only --no-zip`."""
    # Best-effort: remove stale package.json to force regeneration.
    try:
        if os.path.isfile(WEB_PACKAGE_JSON):
            os.remove(WEB_PACKAGE_JSON)
    except OSError:
        pass
    env = os.environ.copy()
    result = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    return result


@pytest.fixture(scope="session")
def reflex_export():
    result = _run_reflex_export()
    yield result


def test_web_package_json_contains_react_quill(reflex_export):
    assert os.path.isfile(WEB_PACKAGE_JSON), (
        f"Expected `{WEB_PACKAGE_JSON}` to exist after `reflex export`. "
        f"Export stdout/stderr: {reflex_export.stdout[-800:]} {reflex_export.stderr[-800:]}"
    )
    with open(WEB_PACKAGE_JSON, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        pytest.fail(f"{WEB_PACKAGE_JSON} is not valid JSON.")
    deps = {}
    for key in ("dependencies", "devDependencies"):
        if isinstance(data.get(key), dict):
            deps.update(data[key])
    found_in_deps = any("react-quill" in name for name in deps.keys())
    found_anywhere = "react-quill" in raw
    assert found_in_deps or found_anywhere, (
        f"Expected `.web/package.json` to declare a `react-quill` dependency. "
        f"Found dependencies: {list(deps.keys())}"
    )


# ------------------------------ Live app test ------------------------------ #

@pytest.fixture(scope="session")
def reflex_server(xprocess, reflex_export):
    class Starter(ProcessStarter):
        name = "reflex_server"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                return s.connect_ex(("localhost", FRONTEND_PORT)) == 0

    xprocess.ensure(Starter.name, Starter)
    # Backend may also need a moment.
    _wait_for_port("localhost", BACKEND_PORT, timeout=120)

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    # Aggressive cleanup of any residual servers.
    for pattern in ("reflex run", "next-server", "next dev", "uvicorn"):
        subprocess.run(["pkill", "-f", pattern], capture_output=True)


def test_index_page_serves_html(reflex_server):
    assert _wait_for_port("localhost", FRONTEND_PORT, timeout=30), (
        f"Reflex frontend did not start listening on port {FRONTEND_PORT}."
    )
    resp = requests.get(f"http://localhost:{FRONTEND_PORT}/", timeout=30)
    assert resp.status_code == 200, (
        f"Expected 200 from index page, got {resp.status_code}."
    )
    body = resp.text.lower()
    assert "<html" in body, "Index page response did not contain an HTML document."
