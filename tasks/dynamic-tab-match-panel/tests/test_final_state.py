import ast
import os
import re
import shutil
import subprocess

import pytest


PROJECT_DIR = "/home/user/myproject"
STATIC_DIR = os.path.join(PROJECT_DIR, ".web", "_static")

EXPORT_TIMEOUT_SEC = 600


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kill_background_servers() -> None:
    """Best-effort kill any leftover reflex / next / node processes."""
    for pattern in (
        "reflex run",
        "reflex export",
        "next dev",
        "next start",
        "uvicorn",
    ):
        subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture(scope="session", autouse=True)
def _cleanup_background_servers():
    """Ensure we never leak background servers."""
    _kill_background_servers()
    yield
    _kill_background_servers()


def _iter_source_files():
    """Yield absolute paths to all .py files under the project that are not
    inside the virtual environment or generated frontend directories."""
    skip_dirs = {".venv", "venv", ".web", "__pycache__", ".git"}
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if fname.endswith(".py"):
                yield os.path.join(root, fname)


def _read_all_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in _iter_source_files():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fp:
                sources[path] = fp.read()
        except OSError:
            continue
    return sources


def _parse_modules() -> dict[str, ast.AST]:
    modules: dict[str, ast.AST] = {}
    for path, src in _read_all_sources().items():
        try:
            modules[path] = ast.parse(src)
        except SyntaxError:
            continue
    return modules


def _is_rx_call(node: ast.AST, name: str) -> bool:
    """Return True for nodes like `rx.<name>(...)`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == name
        and isinstance(func.value, ast.Name)
        and func.value.id == "rx"
    )


def _is_rx_attribute(node: ast.AST, name: str) -> bool:
    """Return True for nodes like `rx.<name>` (an Attribute, not a Call)."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == "rx"
    )


def _string_const(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _bases_reference_rx_state(class_node: ast.ClassDef) -> bool:
    for base in class_node.bases:
        # rx.State
        if isinstance(base, ast.Attribute) and base.attr == "State" and \
                isinstance(base.value, ast.Name) and base.value.id == "rx":
            return True
        # Subclasses of rx.State (rx.Base etc. don't count) — be lenient:
        # accept any base whose attribute name is "State" on rx.
    return False


# ---------------------------------------------------------------------------
# Project layout
# ---------------------------------------------------------------------------


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_pyproject_toml_exists():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), (
        f"Expected uv-managed Reflex project to contain {pyproject}."
    )


def test_rxconfig_exists():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), (
        f"Expected Reflex project root to contain {rxconfig}."
    )


# ---------------------------------------------------------------------------
# State / source-code checks
# ---------------------------------------------------------------------------


def test_active_tab_state_var_defined():
    """A class subclassing rx.State must define active_tab: str = "profile"."""
    modules = _parse_modules()
    assert modules, "No Python source files were found in the project."

    found = False
    for path, tree in modules.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not _bases_reference_rx_state(node):
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(
                    stmt.target, ast.Name
                ) and stmt.target.id == "active_tab":
                    # Annotation must mention str
                    annotation_src = ast.unparse(stmt.annotation) if stmt.annotation else ""
                    if "str" not in annotation_src:
                        continue
                    if stmt.value is None:
                        continue
                    if _string_const(stmt.value) == "profile":
                        found = True
                        break
            if found:
                break
        if found:
            break

    assert found, (
        'Could not find a class subclassing rx.State that declares '
        '`active_tab: str = "profile"`. Searched files: '
        + ", ".join(sorted(modules.keys()))
    )


def test_three_tab_buttons_exist():
    """Three rx.button(...) calls with labels 'Profile', 'Settings', 'About'."""
    modules = _parse_modules()
    required = {"Profile", "Settings", "About"}
    found_labels: set[str] = set()

    for tree in modules.values():
        for node in ast.walk(tree):
            if not _is_rx_call(node, "button"):
                continue
            for arg in node.args:
                label = _string_const(arg)
                if label in required:
                    found_labels.add(label)

    missing = required - found_labels
    assert not missing, (
        f"Missing rx.button(...) calls with labels: {sorted(missing)}. "
        f"Found: {sorted(found_labels)}."
    )


def test_rx_match_uses_active_tab_with_three_cases_and_default():
    """rx.match(<...active_tab>, (\"profile\", ...), (\"settings\", ...),
    (\"about\", ...), <default>)"""
    modules = _parse_modules()
    required_cases = {"profile", "settings", "about"}

    for tree in modules.values():
        for node in ast.walk(tree):
            if not _is_rx_call(node, "match"):
                continue
            if not node.args:
                continue
            cond = node.args[0]
            # First argument must reference an attribute named `active_tab`.
            references_active_tab = False
            for sub in ast.walk(cond):
                if isinstance(sub, ast.Attribute) and sub.attr == "active_tab":
                    references_active_tab = True
                    break
            if not references_active_tab:
                continue

            tuple_case_labels: set[str] = set()
            non_tuple_default = False
            for case_arg in node.args[1:]:
                if isinstance(case_arg, ast.Tuple) and len(case_arg.elts) >= 2:
                    label = _string_const(case_arg.elts[0])
                    if label in required_cases:
                        tuple_case_labels.add(label)
                else:
                    # The last non-tuple argument is the default branch.
                    non_tuple_default = True

            if required_cases.issubset(tuple_case_labels) and non_tuple_default:
                return

    pytest.fail(
        "Did not find an `rx.match(<...active_tab>, ...)` call with explicit "
        'case tuples for "profile", "settings", and "about" plus a non-tuple '
        "default branch."
    )


def test_event_handlers_set_active_tab():
    """Either (a) three handlers each assigning a specific literal, or
    (b) one parameterized handler that assigns self.active_tab = <param>."""
    modules = _parse_modules()
    required_literals = {"profile", "settings", "about"}
    literal_handlers: set[str] = set()
    has_parameterized = False

    for tree in modules.values():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [a.arg for a in node.args.args]
            for body_node in ast.walk(node):
                if not isinstance(body_node, ast.Assign):
                    continue
                for target in body_node.targets:
                    if not (
                        isinstance(target, ast.Attribute)
                        and target.attr == "active_tab"
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        continue
                    literal = _string_const(body_node.value)
                    if literal in required_literals:
                        literal_handlers.add(literal)
                    elif (
                        isinstance(body_node.value, ast.Name)
                        and body_node.value.id in params
                    ):
                        has_parameterized = True

    assert has_parameterized or required_literals.issubset(literal_handlers), (
        "Expected either (a) three handlers assigning self.active_tab to "
        '"profile", "settings", "about" respectively, or (b) one '
        "parameterized handler that assigns self.active_tab = <param>. "
        f"Literal handlers found: {sorted(literal_handlers)}; "
        f"parameterized handler found: {has_parameterized}."
    )


def test_buttons_bind_on_click():
    """Each tab button's call must include on_click=<some handler>."""
    modules = _parse_modules()
    required = {"Profile", "Settings", "About"}
    bound: set[str] = set()

    for tree in modules.values():
        for node in ast.walk(tree):
            if not _is_rx_call(node, "button"):
                continue
            label = None
            for arg in node.args:
                literal = _string_const(arg)
                if literal in required:
                    label = literal
                    break
            if label is None:
                continue
            has_on_click = any(kw.arg == "on_click" for kw in node.keywords)
            if has_on_click:
                bound.add(label)

    missing = required - bound
    assert not missing, (
        f"The following rx.button(...) calls do not have `on_click=` bound: "
        f"{sorted(missing)}."
    )


# ---------------------------------------------------------------------------
# Frontend compilation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def exported_static_dir():
    """Run `uv run reflex export --frontend-only --no-zip` and yield the
    static output directory."""
    # Clean any stale output to ensure we're checking a fresh build.
    if os.path.isdir(STATIC_DIR):
        shutil.rmtree(STATIC_DIR, ignore_errors=True)

    result = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=EXPORT_TIMEOUT_SEC,
        check=False,
    )

    assert result.returncode == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed with exit "
        f"code {result.returncode}.\nSTDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert os.path.isdir(STATIC_DIR), (
        f"Expected Reflex to produce a static frontend bundle at {STATIC_DIR}, "
        "but it was not created."
    )

    yield STATIC_DIR

    _kill_background_servers()


def _bundle_contains(static_dir: str, needle: str) -> bool:
    needle_bytes = needle.encode("utf-8")
    for root, _dirs, files in os.walk(static_dir):
        for fname in files:
            path = os.path.join(root, fname)
            try:
                with open(path, "rb") as fp:
                    if needle_bytes in fp.read():
                        return True
            except OSError:
                continue
    return False


@pytest.mark.parametrize(
    "literal",
    ["User Profile Page", "Settings Page", "About Page"],
)
def test_compiled_bundle_contains_panel_literal(exported_static_dir, literal):
    assert _bundle_contains(exported_static_dir, literal), (
        f"Expected the compiled Reflex frontend bundle at "
        f"{exported_static_dir} to contain the literal {literal!r}, but it "
        "was not found in any file."
    )
