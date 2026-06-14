import ast
import json
import os
import re
import socket
import subprocess
import textwrap
from pathlib import Path
from typing import Iterator

import pytest


PROJECT_DIR = "/home/user/audio_app"
RX_CONFIG = os.path.join(PROJECT_DIR, "rxconfig.py")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
EXCLUDE_DIR_NAMES = {".web", ".venv", "venv", "__pycache__", ".git", "node_modules"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_project_py_files() -> Iterator[Path]:
    project = Path(PROJECT_DIR)
    if not project.is_dir():
        return
    for path in project.rglob("*.py"):
        parts = set(path.relative_to(project).parts)
        if parts & EXCLUDE_DIR_NAMES:
            continue
        yield path


def _parse_py_files() -> list[tuple[Path, ast.Module]]:
    parsed: list[tuple[Path, ast.Module]] = []
    for path in _iter_project_py_files():
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            parsed.append((path, ast.parse(source)))
        except SyntaxError:
            continue
    return parsed


def _all_classdefs(modules: list[tuple[Path, ast.Module]]) -> list[tuple[Path, ast.ClassDef]]:
    classes: list[tuple[Path, ast.ClassDef]] = []
    for path, tree in modules:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append((path, node))
    return classes


def _base_names(cls: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in cls.bases:
        names.append(ast.unparse(base))
    return names


def _annotation_src(annassign: ast.AnnAssign) -> str:
    return ast.unparse(annassign.annotation)


def _find_assign_value(cls: ast.ClassDef, target_name: str):
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == target_name:
                    return stmt.value
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) \
                and stmt.target.id == target_name:
            return stmt.value
    return None


def _find_annassign(cls: ast.ClassDef, target_name: str) -> ast.AnnAssign | None:
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) \
                and stmt.target.id == target_name:
            return stmt
    return None


def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def parsed_modules() -> list[tuple[Path, ast.Module]]:
    modules = _parse_py_files()
    assert modules, (
        f"No parsable Python source files found under {PROJECT_DIR}. "
        "The agent must create a Reflex project here."
    )
    return modules


@pytest.fixture(scope="module")
def wrapper_class(parsed_modules) -> ast.ClassDef:
    """Return the NoSSRComponent subclass that wraps react-h5-audio-player."""
    candidates: list[ast.ClassDef] = []
    for _, cls in _all_classdefs(parsed_modules):
        bases = _base_names(cls)
        if any(b.split(".")[-1] == "NoSSRComponent" for b in bases):
            # Must also reference react-h5-audio-player as its library.
            lib_value = _find_assign_value(cls, "library")
            if isinstance(lib_value, ast.Constant) and isinstance(lib_value.value, str):
                head = lib_value.value.split("@", 1)[0].strip()
                if head == "react-h5-audio-player":
                    candidates.append(cls)
    assert candidates, (
        "No class directly subclassing NoSSRComponent with "
        "library='react-h5-audio-player' was found in the project sources."
    )
    return candidates[0]


@pytest.fixture(scope="module")
def state_class(parsed_modules) -> ast.ClassDef:
    """Return a class subclassing rx.State (or any *State* base)."""
    candidates: list[ast.ClassDef] = []
    for _, cls in _all_classdefs(parsed_modules):
        bases = _base_names(cls)
        if any(b == "rx.State" or b.endswith(".State") or b == "State" for b in bases):
            # Must define current_index annotated as int.
            ann = _find_annassign(cls, "current_index")
            if ann is not None:
                ann_src = _annotation_src(ann)
                if "int" in ann_src:
                    candidates.append(cls)
    assert candidates, (
        "No rx.State subclass defining `current_index: int` was found. "
        "The playlist State machine is missing."
    )
    return candidates[0]


# ---------------------------------------------------------------------------
# Project layout
# ---------------------------------------------------------------------------


def test_rxconfig_exists():
    assert os.path.isfile(RX_CONFIG), (
        f"Reflex project not initialized: missing {RX_CONFIG}. "
        "Run `uv run reflex init --template blank` in the project directory."
    )


def test_requirements_lists_reflex():
    assert os.path.isfile(REQUIREMENTS_FILE), (
        f"requirements.txt missing at {REQUIREMENTS_FILE}. "
        "Generate it with `uv pip freeze > requirements.txt`."
    )
    content = Path(REQUIREMENTS_FILE).read_text(encoding="utf-8").lower()
    assert re.search(r"^\s*reflex(\b|==|>=|~=|@|\s)", content, re.MULTILINE), (
        "requirements.txt must list `reflex` as a dependency for Reflex Cloud compatibility."
    )


def test_ports_free_before_checks():
    assert _is_port_free(3000), (
        "TCP port 3000 is still bound after the task finished; "
        "the agent must kill all background Reflex servers (frontend)."
    )
    assert _is_port_free(8000), (
        "TCP port 8000 is still bound after the task finished; "
        "the agent must kill all background Reflex servers (backend)."
    )


# ---------------------------------------------------------------------------
# Wrapper static analysis
# ---------------------------------------------------------------------------


def test_wrapper_library_is_react_h5_audio_player(wrapper_class: ast.ClassDef):
    lib_value = _find_assign_value(wrapper_class, "library")
    assert isinstance(lib_value, ast.Constant) and isinstance(lib_value.value, str), (
        "Wrapper class must set `library` to a string literal."
    )
    head = lib_value.value.split("@", 1)[0].strip()
    assert head == "react-h5-audio-player", (
        f"Wrapper `library` must wrap `react-h5-audio-player`, got `{lib_value.value}`."
    )


def test_wrapper_has_tag(wrapper_class: ast.ClassDef):
    tag_value = _find_assign_value(wrapper_class, "tag")
    assert isinstance(tag_value, ast.Constant) and isinstance(tag_value.value, str) \
        and tag_value.value.strip(), (
        "Wrapper class must set a non-empty string `tag` attribute."
    )


def test_wrapper_is_default(wrapper_class: ast.ClassDef):
    is_default = _find_assign_value(wrapper_class, "is_default")
    assert isinstance(is_default, ast.Constant) and is_default.value is True, (
        "Wrapper class must set `is_default = True` because react-h5-audio-player "
        "exports the AudioPlayer component as the default export."
    )


def test_wrapper_declares_src_var(wrapper_class: ast.ClassDef):
    ann = _find_annassign(wrapper_class, "src")
    assert ann is not None, "Wrapper must declare a `src` class attribute."
    src_ann = _annotation_src(ann)
    assert re.search(r"Var\s*\[\s*str\s*\]", src_ann), (
        f"Wrapper `src` must be annotated as rx.Var[str]; got `{src_ann}`."
    )


def test_wrapper_declares_autoplay_var(wrapper_class: ast.ClassDef):
    ann = _find_annassign(wrapper_class, "autoplay")
    assert ann is not None, (
        "Wrapper must declare a `autoplay` class attribute (literal snake_case name)."
    )
    src_ann = _annotation_src(ann)
    assert re.search(r"Var\s*\[\s*bool\s*\]", src_ann), (
        f"Wrapper `autoplay` must be annotated as rx.Var[bool]; got `{src_ann}`."
    )


@pytest.mark.parametrize("event_name", ["on_play", "on_pause", "on_ended"])
def test_wrapper_event_trigger_zero_arg_serializer(wrapper_class: ast.ClassDef, event_name: str):
    ann = _find_annassign(wrapper_class, event_name)
    assert ann is not None, (
        f"Wrapper must declare an event trigger `{event_name}` annotated as `rx.EventHandler[...]`."
    )
    ann_src = _annotation_src(ann)
    assert "EventHandler" in ann_src, (
        f"Annotation for `{event_name}` must reference EventHandler; got `{ann_src}`."
    )
    # Find a Lambda node inside the subscript and verify zero args + empty-list body.
    lambdas = [n for n in ast.walk(ann.annotation) if isinstance(n, ast.Lambda)]
    assert lambdas, (
        f"Event trigger `{event_name}` must use a `lambda: []` serializer inside its "
        f"`rx.EventHandler[...]` subscript."
    )
    lam = lambdas[0]
    args = lam.args
    total_args = (
        len(args.args)
        + len(args.posonlyargs)
        + len(args.kwonlyargs)
        + (1 if args.vararg else 0)
        + (1 if args.kwarg else 0)
    )
    assert total_args == 0, (
        f"Serializer lambda for `{event_name}` must take zero arguments; "
        f"got {total_args}."
    )
    assert isinstance(lam.body, ast.List) and len(lam.body.elts) == 0, (
        f"Serializer lambda for `{event_name}` must return an empty list literal `[]`."
    )


# ---------------------------------------------------------------------------
# State static analysis
# ---------------------------------------------------------------------------


def test_state_current_index_defaults_to_zero(state_class: ast.ClassDef):
    ann = _find_annassign(state_class, "current_index")
    assert ann is not None and isinstance(ann.value, ast.Constant) and ann.value.value == 0, (
        "State must declare `current_index: int = 0` as a Base Var."
    )


def test_state_has_three_track_list(state_class: ast.ClassDef):
    found_3 = False
    for stmt in state_class.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.value, ast.List):
            if len(stmt.value.elts) == 3:
                found_3 = True
                break
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.List):
            if len(stmt.value.elts) == 3:
                found_3 = True
                break
    assert found_3, (
        "State must declare a list-typed Base Var whose default value contains exactly 3 track entries."
    )


def test_state_has_click_handler_setting_current_index(state_class: ast.ClassDef):
    found = False
    for stmt in state_class.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(stmt):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "current_index" \
                            and isinstance(target.value, ast.Name) and target.value.id == "self":
                        # Confirm RHS references one of the function's parameters or
                        # is otherwise a direct Name assignment (the "click" handler).
                        if not isinstance(node.value, ast.BinOp):
                            found = True
                            break
            if found:
                break
        if found:
            break
    assert found, (
        "State must define an event handler that assigns `self.current_index` to "
        "an index parameter (the track-click handler)."
    )


def test_state_has_on_ended_handler_with_modulo_three(state_class: ast.ClassDef):
    found = False
    for stmt in state_class.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(stmt):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "current_index" \
                            and isinstance(target.value, ast.Name) and target.value.id == "self":
                        if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mod):
                            right = node.value.right
                            if isinstance(right, ast.Constant) and right.value == 3:
                                found = True
                                break
            if found:
                break
        if found:
            break
    assert found, (
        "State must define an event handler that advances `self.current_index` using "
        "modulo-3 arithmetic so the playlist wraps from index 2 back to 0."
    )


# ---------------------------------------------------------------------------
# State behaviour smoke test via `uv run python`
# ---------------------------------------------------------------------------


def test_state_behavior_via_uv_run_python(state_class: ast.ClassDef):
    """Drive the State class via `uv run python -c ...` to verify wraparound."""
    state_name = state_class.name

    script = textwrap.dedent(
        f"""
        import sys, os, importlib, pkgutil, inspect, pathlib

        project_root = pathlib.Path("/home/user/audio_app").resolve()
        sys.path.insert(0, str(project_root))

        # Discover the app package: a directory that contains an __init__.py and
        # is not .web/.venv/etc.
        skip = {{".web", ".venv", "venv", "__pycache__", ".git", "node_modules", "alembic"}}
        candidate_pkgs = []
        for child in project_root.iterdir():
            if child.is_dir() and child.name not in skip and (child / "__init__.py").exists():
                candidate_pkgs.append(child.name)

        StateCls = None
        for pkg in candidate_pkgs:
            try:
                mod = importlib.import_module(pkg)
            except Exception:
                continue
            # walk submodules
            for sub in pkgutil.walk_packages(mod.__path__, prefix=pkg + "."):
                try:
                    submod = importlib.import_module(sub.name)
                except Exception:
                    continue
                for name, obj in inspect.getmembers(submod, inspect.isclass):
                    if name == {state_name!r} and obj.__module__.startswith(pkg):
                        StateCls = obj
                        break
                if StateCls is not None:
                    break
            if StateCls is None:
                # Maybe the class lives in the package's __init__ itself.
                for name, obj in inspect.getmembers(mod, inspect.isclass):
                    if name == {state_name!r}:
                        StateCls = obj
                        break
            if StateCls is not None:
                break

        if StateCls is None:
            print("FAIL: could not import State class", {state_name!r}, file=sys.stderr)
            sys.exit(2)

        instance = StateCls()

        # Locate handler that takes an int and assigns to current_index without modulo.
        click_handler_name = None
        ended_handler_name = None
        import ast as _ast, textwrap as _tw
        for attr_name in dir(StateCls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(StateCls, attr_name, None)
            if not callable(attr):
                continue
            try:
                src = _tw.dedent(inspect.getsource(attr))
            except Exception:
                continue
            try:
                tree = _ast.parse(src)
            except Exception:
                continue
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Assign):
                    for target in node.targets:
                        if (isinstance(target, _ast.Attribute) and target.attr == "current_index"
                                and isinstance(target.value, _ast.Name) and target.value.id == "self"):
                            if isinstance(node.value, _ast.BinOp) and isinstance(node.value.op, _ast.Mod):
                                ended_handler_name = ended_handler_name or attr_name
                            else:
                                click_handler_name = click_handler_name or attr_name

        if click_handler_name is None or ended_handler_name is None:
            print(
                "FAIL: could not locate click/ended handlers; click=",
                click_handler_name, "ended=", ended_handler_name,
                file=sys.stderr,
            )
            sys.exit(3)

        # Reflex wraps event handlers in EventHandler descriptors; the raw callable
        # is on the class. We resolve it via instance __class__.__dict__ if needed.
        def _raw(name):
            attr = StateCls.__dict__.get(name) or getattr(StateCls, name)
            fn = getattr(attr, "fn", None) or getattr(attr, "func", None) or attr
            return fn

        click_fn = _raw(click_handler_name)
        ended_fn = _raw(ended_handler_name)

        # Click on index 2
        try:
            click_fn(instance, 2)
        except TypeError:
            click_fn(instance, index=2)
        assert instance.current_index == 2, f"after click_fn(2), current_index={{instance.current_index}}"

        seq = []
        for _ in range(3):
            ended_fn(instance)
            seq.append(instance.current_index)

        expected = [0, 1, 2]
        assert seq == expected, f"on_ended sequence wrong: got {{seq}}, expected {{expected}}"

        print("OK")
        """
    )

    proc = subprocess.run(
        ["uv", "run", "python", "-c", script],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"State behaviour smoke test failed (exit={proc.returncode}).\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    assert "OK" in proc.stdout, (
        f"State behaviour smoke test did not report OK.\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


# ---------------------------------------------------------------------------
# Frontend bundle check
# ---------------------------------------------------------------------------


def test_frontend_export_references_react_h5_audio_player():
    """Build the frontend with `reflex export --frontend-only` and grep the bundle."""
    proc = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (
        f"`reflex export --frontend-only --no-zip` failed (exit={proc.returncode}).\n"
        f"--- stdout (tail) ---\n{proc.stdout[-2000:]}\n"
        f"--- stderr (tail) ---\n{proc.stderr[-2000:]}"
    )

    search_roots = [
        Path(PROJECT_DIR) / ".web" / "_static",
        Path(PROJECT_DIR) / ".web" / ".next",
        Path(PROJECT_DIR) / ".web",
    ]
    needle = "react-h5-audio-player"
    text_exts = {".js", ".mjs", ".cjs", ".html", ".css", ".json", ".map", ".txt"}

    found = False
    scanned_files = 0
    for root in search_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in text_exts:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            scanned_files += 1
            if needle in content:
                found = True
                break
        if found:
            break

    assert found, (
        f"After `reflex export`, the string `{needle}` was not found in any compiled "
        f"frontend asset under {PROJECT_DIR}/.web. Scanned {scanned_files} text files."
    )


# ---------------------------------------------------------------------------
# Teardown sanity check
# ---------------------------------------------------------------------------


def test_no_lingering_processes_on_reflex_ports():
    """Re-check after the export step that the agent left no Reflex servers running."""
    assert _is_port_free(3000), (
        "Port 3000 is bound after verification — the agent must kill all background Reflex servers."
    )
    assert _is_port_free(8000), (
        "Port 8000 is bound after verification — the agent must kill all background Reflex servers."
    )
