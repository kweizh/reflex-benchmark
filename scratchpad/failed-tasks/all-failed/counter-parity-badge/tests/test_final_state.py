import ast
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


PROJECT_DIR = Path("/home/user/myproject")


def _kill_reflex_processes() -> None:
    """Best-effort kill of any leftover reflex / next dev servers."""
    for pattern in ("reflex", "next dev", "next-server"):
        subprocess.run(
            ["pkill", "-f", pattern],
            check=False,
            capture_output=True,
        )
    time.sleep(0.5)


def _load_app_name() -> str:
    rxconfig = PROJECT_DIR / "rxconfig.py"
    assert rxconfig.is_file(), (
        f"Expected rxconfig.py at {rxconfig}; was the project initialized "
        f"with `uv run reflex init --template blank`?"
    )
    tree = ast.parse(rxconfig.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (
                    kw.arg == "app_name"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    return kw.value.value
    raise AssertionError("Could not determine `app_name` from rxconfig.py")


def _main_module_path() -> Path:
    app_name = _load_app_name()
    candidate = PROJECT_DIR / app_name / f"{app_name}.py"
    assert candidate.is_file(), (
        f"Expected Reflex entry module at {candidate}"
    )
    return candidate


def _parse_main_module() -> ast.Module:
    return ast.parse(_main_module_path().read_text())


def _state_classes(tree: ast.Module) -> list[ast.ClassDef]:
    states: list[ast.ClassDef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if (
                    isinstance(base, ast.Attribute)
                    and base.attr == "State"
                    and isinstance(base.value, ast.Name)
                    and base.value.id in {"rx", "reflex"}
                ):
                    states.append(node)
                    break
    return states


def _state_class_with_count() -> ast.ClassDef:
    tree = _parse_main_module()
    for state in _state_classes(tree):
        for item in state.body:
            if (
                isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and item.target.id == "count"
            ):
                return state
    raise AssertionError(
        "Could not find a State subclass declaring a `count` base var."
    )


def test_state_class_with_count_int_zero():
    tree = _parse_main_module()
    states = _state_classes(tree)
    assert states, (
        "Expected at least one class subclassing `rx.State` or `reflex.State` "
        "in the main app module."
    )
    for state in states:
        for item in state.body:
            if not isinstance(item, ast.AnnAssign):
                continue
            if (
                isinstance(item.target, ast.Name)
                and item.target.id == "count"
                and isinstance(item.annotation, ast.Name)
                and item.annotation.id == "int"
                and isinstance(item.value, ast.Constant)
                and item.value.value == 0
            ):
                return
    raise AssertionError(
        "Expected a State subclass with annotated base var `count: int = 0`."
    )


def test_three_event_handlers_for_count():
    state = _state_class_with_count()
    has_inc = has_dec = has_reset = False
    for item in state.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(item):
            if isinstance(sub, ast.AugAssign):
                tgt = sub.target
                if (
                    isinstance(tgt, ast.Attribute)
                    and tgt.attr == "count"
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                    and isinstance(sub.value, ast.Constant)
                    and sub.value.value == 1
                ):
                    if isinstance(sub.op, ast.Add):
                        has_inc = True
                    elif isinstance(sub.op, ast.Sub):
                        has_dec = True
            elif isinstance(sub, ast.Assign):
                for tgt in sub.targets:
                    if (
                        isinstance(tgt, ast.Attribute)
                        and tgt.attr == "count"
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "self"
                        and isinstance(sub.value, ast.Constant)
                        and sub.value.value == 0
                    ):
                        has_reset = True
    assert has_inc, (
        "Expected one event handler whose body performs `self.count += 1`."
    )
    assert has_dec, (
        "Expected one event handler whose body performs `self.count -= 1`."
    )
    assert has_reset, (
        "Expected one event handler whose body assigns `self.count = 0`."
    )


def test_parity_cached_computed_var():
    state = _state_class_with_count()
    for item in state.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if item.name != "parity":
            continue
        for dec in item.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "var"
                and isinstance(func.value, ast.Name)
                and func.value.id in {"rx", "reflex"}
            ):
                continue
            cache_kw = next(
                (kw for kw in dec.keywords if kw.arg == "cache"),
                None,
            )
            if cache_kw is None or not (
                isinstance(cache_kw.value, ast.Constant)
                and cache_kw.value.value is True
            ):
                continue
            string_consts = {
                n.value
                for n in ast.walk(item)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            }
            assert "even" in string_consts and "odd" in string_consts, (
                "Cached computed var `parity` must return both 'even' and "
                f"'odd'; found string literals: {sorted(string_consts)!r}"
            )
            return
    raise AssertionError(
        "Expected a cached computed var `parity` decorated with "
        "`@rx.var(cache=True)` on the State class."
    )


def test_rx_cond_used_in_layout():
    tree = _parse_main_module()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "cond"
                and isinstance(func.value, ast.Name)
                and func.value.id in {"rx", "reflex"}
            ):
                return
    raise AssertionError(
        "Expected at least one `rx.cond(...)` call to color-code the badge "
        "based on the parity computed var."
    )


@pytest.fixture(scope="session")
def exported_frontend():
    """Run `uv run reflex export --frontend-only --no-zip` and yield the
    static export dir. Always kill any reflex processes during teardown.
    """
    _kill_reflex_processes()

    static_dir = PROJECT_DIR / ".web" / "_static"
    if static_dir.exists():
        shutil.rmtree(static_dir, ignore_errors=True)

    env = os.environ.copy()
    env.setdefault("CI", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")

    proc = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )

    try:
        yield {"proc": proc, "static_dir": static_dir}
    finally:
        _kill_reflex_processes()


def test_frontend_export_succeeds(exported_frontend):
    proc = exported_frontend["proc"]
    static_dir: Path = exported_frontend["static_dir"]
    assert proc.returncode == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed with "
        f"exit code {proc.returncode}.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert static_dir.is_dir(), (
        f"Expected exported frontend assets under {static_dir} after "
        "`reflex export`."
    )


def test_frontend_contains_required_literals(exported_frontend):
    static_dir: Path = exported_frontend["static_dir"]
    assert static_dir.is_dir(), (
        f"Frontend static dir missing: {static_dir}"
    )
    needles = ["Increment", "Decrement", "Reset", "Count:"]
    found = {n: False for n in needles}
    for path in static_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8", errors="ignore")
        except OSError:
            continue
        for n in needles:
            if not found[n] and n in text:
                found[n] = True
        if all(found.values()):
            break
    missing = sorted(n for n, ok in found.items() if not ok)
    assert not missing, (
        "Exported frontend bundle is missing required visible literals: "
        f"{missing}. All four of 'Increment', 'Decrement', 'Reset', and "
        "'Count:' must appear in the compiled frontend under "
        f"{static_dir}."
    )


def test_no_reflex_servers_running_after_teardown(exported_frontend):
    """Sanity check: after the export fixture's teardown runs (at the end
    of the session), no reflex / next-server process owned by this user
    should remain. This test depends on the fixture so it can read its
    stdout, but the actual cleanup happens in finalization."""
    # Run the kill once more defensively and confirm.
    _kill_reflex_processes()
    result = subprocess.run(
        ["pgrep", "-af", "reflex"],
        capture_output=True,
        text=True,
        check=False,
    )
    # pgrep returns 1 when no matches; treat as success.
    leftover = [
        line
        for line in result.stdout.splitlines()
        if "reflex export" not in line and "pgrep" not in line and line.strip()
    ]
    assert not leftover, (
        "Background reflex processes remained after teardown: "
        f"{leftover!r}"
    )
