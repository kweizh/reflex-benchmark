"""Final-state checks for the wrap-react-colorful task.

These tests run with the system python3 (Reflex is NOT installed in the system
python), so we only rely on the standard library, the AST module, and
`subprocess` to invoke the user-managed `uv` environment when we need to
actually build the Reflex frontend.
"""

import ast
import json
import os
import shutil
import socket
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/myproject"
WEB_PACKAGE_JSON = os.path.join(PROJECT_DIR, ".web", "package.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_project_py_files():
    """Yield every .py file inside the project, skipping vendored dirs."""
    skip_dirs = {".web", ".venv", "venv", "__pycache__", ".git", "node_modules"}
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


def _parse_all():
    """Return list of (path, ast.Module) for every project python file."""
    parsed = []
    for path in _iter_project_py_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            parsed.append((path, ast.parse(source)))
        except (SyntaxError, UnicodeDecodeError):
            # ignore generated/broken files; the user's source must parse.
            continue
    return parsed


def _find_class(parsed, class_name):
    for path, tree in parsed:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return path, tree, node
    return None


def _base_names(class_node):
    names = []
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            # e.g. rx.State -> "rx.State"
            parts = []
            cur = base
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            names.append(".".join(reversed(parts)))
    return names


def _class_assigns(class_node):
    """Yield (target_name, value_node, annotation_node_or_None) for class-level assigns."""
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            yield stmt.target.id, stmt.value, stmt.annotation
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    yield tgt.id, stmt.value, None


def _annotation_text(node):
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _kill_background_servers():
    for pattern in ("reflex run", "next-server", "next dev", "reflex export"):
        subprocess.run(
            ["pkill", "-f", pattern], capture_output=True, text=True
        )


def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return False
        except (ConnectionRefusedError, OSError):
            return True


# ---------------------------------------------------------------------------
# Build the frontend so .web/package.json is materialized
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _build_frontend():
    # 1. Make sure no leftover servers are running.
    _kill_background_servers()

    # 2. Drop any stale .web so the export step truly regenerates package.json.
    web_dir = os.path.join(PROJECT_DIR, ".web")
    if os.path.isdir(web_dir):
        shutil.rmtree(web_dir, ignore_errors=True)

    uv = shutil.which("uv")
    assert uv is not None, "uv binary must be available to build the Reflex frontend."

    env = os.environ.copy()
    env.setdefault("REFLEX_TELEMETRY_ENABLED", "false")

    # 3. Run `uv run reflex export --frontend-only --no-zip`.
    result = subprocess.run(
        [uv, "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )

    yield {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

    # Final cleanup so the host ports are free.
    _kill_background_servers()
    time.sleep(1)


# ---------------------------------------------------------------------------
# AST tests
# ---------------------------------------------------------------------------


def test_project_python_files_present():
    files = list(_iter_project_py_files())
    assert files, f"No python source files found under {PROJECT_DIR}."


def test_nossr_component_imported_from_reflex_components_component():
    found = False
    for _, tree in _parse_all():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "reflex.components.component":
                for alias in node.names:
                    if alias.name == "NoSSRComponent":
                        found = True
                        break
            if found:
                break
        if found:
            break
    assert found, (
        "Expected `from reflex.components.component import NoSSRComponent` "
        "somewhere in the project's Python source."
    )


def test_color_picker_class_inherits_nossr_component():
    found = _find_class(_parse_all(), "ColorPicker")
    assert found is not None, "Could not find a class named `ColorPicker` in the project."
    _, _, cls = found
    bases = _base_names(cls)
    assert "NoSSRComponent" in bases, (
        f"`ColorPicker` must inherit from `NoSSRComponent`, but found bases: {bases}"
    )


def test_color_picker_library_and_tag():
    found = _find_class(_parse_all(), "ColorPicker")
    assert found is not None, "Missing class `ColorPicker`."
    _, _, cls = found

    library_value = None
    tag_value = None
    for name, value, _ann in _class_assigns(cls):
        if name == "library" and isinstance(value, ast.Constant):
            library_value = value.value
        elif name == "tag" and isinstance(value, ast.Constant):
            tag_value = value.value

    assert isinstance(library_value, str), (
        "ColorPicker.library must be assigned to a string literal."
    )
    assert "react-colorful" in library_value, (
        f"ColorPicker.library must reference `react-colorful`, got: {library_value!r}"
    )
    assert "5.7.0" in library_value, (
        f"ColorPicker.library must pin version `5.7.0`, got: {library_value!r}"
    )
    assert tag_value == "HexColorPicker", (
        f"ColorPicker.tag must be the string 'HexColorPicker', got: {tag_value!r}"
    )


def test_color_picker_color_prop_is_var_str():
    found = _find_class(_parse_all(), "ColorPicker")
    assert found is not None
    _, _, cls = found

    annotation_text = None
    for name, _value, ann in _class_assigns(cls):
        if name == "color" and ann is not None:
            annotation_text = _annotation_text(ann)
            break

    assert annotation_text is not None, (
        "ColorPicker must declare an annotated prop `color`."
    )
    normalized = annotation_text.replace(" ", "")
    assert ("rx.Var[str]" in normalized) or ("Var[str]" in normalized), (
        f"ColorPicker.color must be annotated as `rx.Var[str]`, got: {annotation_text!r}"
    )


def test_color_picker_on_change_event_handler_lambda():
    found = _find_class(_parse_all(), "ColorPicker")
    assert found is not None
    _, _, cls = found

    annotation = None
    for name, _value, ann in _class_assigns(cls):
        if name == "on_change" and ann is not None:
            annotation = ann
            break

    assert annotation is not None, (
        "ColorPicker must declare an annotated event trigger `on_change`."
    )

    # annotation should be Subscript: rx.EventHandler[<lambda>]
    assert isinstance(annotation, ast.Subscript), (
        f"`on_change` annotation must be a subscript like `rx.EventHandler[...]`, "
        f"got: {_annotation_text(annotation)!r}"
    )

    outer = annotation.value
    outer_text = _annotation_text(outer).replace(" ", "")
    assert outer_text.endswith("EventHandler"), (
        f"`on_change` must use `rx.EventHandler[...]`, got: {_annotation_text(annotation)!r}"
    )

    slice_node = annotation.slice
    # In Python 3.9+ the slice is the raw node (no ast.Index wrapper).
    if hasattr(ast, "Index") and isinstance(slice_node, ast.Index):  # pragma: no cover
        slice_node = slice_node.value  # type: ignore[attr-defined]

    assert isinstance(slice_node, ast.Lambda), (
        f"`on_change` EventHandler arg must be a lambda, got: {_annotation_text(slice_node)!r}"
    )

    args = slice_node.args
    pos_args = list(args.args)
    assert len(pos_args) == 1 and not args.vararg and not args.kwarg, (
        f"`on_change` lambda must take exactly one positional argument, got: "
        f"{_annotation_text(slice_node)!r}"
    )
    assert pos_args[0].arg == "color", (
        f"`on_change` lambda's argument must be named `color`, got: {pos_args[0].arg!r}"
    )

    body = slice_node.body
    assert isinstance(body, ast.List), (
        f"`on_change` lambda body must be a list literal `[color]`, got: "
        f"{_annotation_text(body)!r}"
    )
    assert len(body.elts) == 1 and isinstance(body.elts[0], ast.Name) and body.elts[0].id == "color", (
        f"`on_change` lambda must return `[color]`, got: {_annotation_text(body)!r}"
    )


def test_color_picker_factory_assignment():
    parsed = _parse_all()
    found = False
    for _path, tree in parsed:
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                value = node.value
                if (
                    isinstance(tgt, ast.Name)
                    and tgt.id == "color_picker"
                    and isinstance(value, ast.Attribute)
                    and value.attr == "create"
                    and isinstance(value.value, ast.Name)
                    and value.value.id == "ColorPicker"
                ):
                    found = True
                    break
        if found:
            break
    assert found, (
        "Expected a module-level assignment `color_picker = ColorPicker.create`."
    )


def test_state_class_color_var_and_set_color_handler():
    parsed = _parse_all()

    state_class = None
    for _path, tree in parsed:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = _base_names(node)
                if "rx.State" in bases or "State" in bases:
                    state_class = node
                    break
        if state_class is not None:
            break

    assert state_class is not None, "Could not find a class inheriting from rx.State."

    # color: str = "#ff0000"
    color_ok = False
    for stmt in state_class.body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "color"
            and stmt.value is not None
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value == "#ff0000"
        ):
            ann_text = _annotation_text(stmt.annotation)
            if "str" in ann_text:
                color_ok = True
                break
    assert color_ok, (
        "State class must declare `color: str = \"#ff0000\"`."
    )

    # set_color(self, c: str) that assigns to self.color
    set_color_ok = False
    for stmt in state_class.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "set_color":
            args = stmt.args.args
            if len(args) != 2:
                continue
            if args[0].arg != "self":
                continue
            second_ann = _annotation_text(args[1].annotation)
            if "str" not in second_ann:
                continue
            param_name = args[1].arg
            for inner in ast.walk(stmt):
                if isinstance(inner, ast.Assign):
                    for tgt in inner.targets:
                        if (
                            isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "self"
                            and tgt.attr == "color"
                            and isinstance(inner.value, ast.Name)
                            and inner.value.id == param_name
                        ):
                            set_color_ok = True
                            break
                if set_color_ok:
                    break
            if set_color_ok:
                break
    assert set_color_ok, (
        "State class must define `set_color(self, c: str)` that assigns its parameter to `self.color`."
    )


# ---------------------------------------------------------------------------
# Build artifact tests
# ---------------------------------------------------------------------------


def test_reflex_export_succeeded(_build_frontend):
    assert _build_frontend["returncode"] == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed.\n"
        f"stdout:\n{_build_frontend['stdout']}\n"
        f"stderr:\n{_build_frontend['stderr']}"
    )


def test_web_package_json_exists():
    assert os.path.isfile(WEB_PACKAGE_JSON), (
        f"Expected {WEB_PACKAGE_JSON} to exist after building the frontend."
    )


def test_web_package_json_contains_react_colorful():
    with open(WEB_PACKAGE_JSON, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    deps = pkg.get("dependencies") or {}
    # The package must be in dependencies; the wrapped library tag is exactly
    # `react-colorful`.
    assert "react-colorful" in deps, (
        f"Expected `react-colorful` in .web/package.json dependencies, got keys: {sorted(deps)}"
    )

    # Also ensure the raw JSON text contains the string (defensive check).
    with open(WEB_PACKAGE_JSON, "r", encoding="utf-8") as f:
        raw = f.read()
    assert "react-colorful" in raw, (
        ".web/package.json must mention `react-colorful` somewhere."
    )


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def test_ports_free_after_build():
    _kill_background_servers()
    time.sleep(1)
    assert _port_free(3000), "Port 3000 must be free after evaluation (reflex frontend must be stopped)."
    assert _port_free(8000), "Port 8000 must be free after evaluation (reflex backend must be stopped)."
