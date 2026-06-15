import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/myproject"
WEB_DIR = os.path.join(PROJECT_DIR, ".web")
EXCLUDE_DIR_NAMES = {".venv", ".web", "__pycache__", "node_modules", ".git"}


def _iter_python_source_files(root):
    """Yield Python source files under `root`, excluding vendored/build dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        # prune in-place so os.walk doesn't descend into excluded directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for fname in filenames:
            if fname.endswith(".py"):
                yield os.path.join(dirpath, fname)


def _read_all_python_sources():
    contents = {}
    for path in _iter_python_source_files(PROJECT_DIR):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                contents[path] = f.read()
        except OSError:
            continue
    return contents


def _iter_exported_frontend_files(root):
    """Yield text-like files under the exported frontend directory."""
    text_exts = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".html",
        ".json",
        ".css",
        ".map",
        ".txt",
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {"node_modules", ".git"}]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in text_exts:
                yield os.path.join(dirpath, fname)


@pytest.fixture(scope="module")
def python_sources():
    sources = _read_all_python_sources()
    assert sources, (
        f"No Python source files found under {PROJECT_DIR}. "
        "Expected a Reflex project to exist there."
    )
    return sources


@pytest.fixture(scope="module")
def export_frontend():
    """
    Run `uv run reflex export --frontend-only --no-zip` in the project dir.
    Yields the path to the resulting `.web` directory.
    Always tries to clean up any leftover background server processes.
    """
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; cannot run `uv run reflex export`."
    )
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )

    # Best-effort: kill any leftover Reflex/Next dev servers before exporting.
    for pattern in ("reflex run", "reflex export", "next dev", "next start"):
        subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )

    try:
        result = subprocess.run(
            ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            "`uv run reflex export --frontend-only --no-zip` timed out after "
            f"600 seconds. stdout: {exc.stdout!r} stderr: {exc.stderr!r}"
        )

    assert result.returncode == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed with exit "
        f"code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert os.path.isdir(WEB_DIR), (
        f"Expected exported frontend directory at {WEB_DIR} after running "
        "`reflex export --frontend-only --no-zip`."
    )

    yield WEB_DIR

    # Teardown: kill anything the export or task may have spawned.
    for pattern in (
        "reflex run",
        "reflex export",
        "next dev",
        "next start",
        "node .*next",
    ):
        subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )


def test_project_layout_exists():
    """The Reflex project must exist with the standard pyproject + rxconfig files."""
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(pyproject), (
        f"Missing {pyproject}; project must be initialized with `uv init`."
    )
    assert os.path.isfile(rxconfig), (
        f"Missing {rxconfig}; project must be initialized with "
        "`uv run reflex init --template blank`."
    )


def test_rx_cookie_default_and_name(python_sources):
    """
    There must be an `rx.Cookie(...)` call that supplies both the default
    string "light" and the keyword `name="app_theme"` (in either order).
    """
    pattern_light_first = re.compile(
        r"rx\.Cookie\s*\(\s*[\"']light[\"']\s*,\s*name\s*=\s*[\"']app_theme[\"']\s*\)"
    )
    pattern_name_first = re.compile(
        r"rx\.Cookie\s*\(\s*name\s*=\s*[\"']app_theme[\"']\s*,\s*[\"']light[\"']\s*\)"
    )
    # Also tolerate `default="light"` style if the agent uses it.
    pattern_default_kw = re.compile(
        r"rx\.Cookie\s*\([^)]*default\s*=\s*[\"']light[\"'][^)]*name\s*=\s*[\"']app_theme[\"'][^)]*\)"
    )
    pattern_default_kw_alt = re.compile(
        r"rx\.Cookie\s*\([^)]*name\s*=\s*[\"']app_theme[\"'][^)]*default\s*=\s*[\"']light[\"'][^)]*\)"
    )

    matched_file = None
    for path, content in python_sources.items():
        if (
            pattern_light_first.search(content)
            or pattern_name_first.search(content)
            or pattern_default_kw.search(content)
            or pattern_default_kw_alt.search(content)
        ):
            matched_file = path
            break

    assert matched_file is not None, (
        "Could not find an `rx.Cookie(...)` call with both default value "
        '"light" and keyword argument name="app_theme" in any Python source '
        f"under {PROJECT_DIR}."
    )


def test_theme_field_uses_rx_cookie(python_sources):
    """
    There must be a state field literally named `theme` that is assigned an
    `rx.Cookie(...)` value (with optional type annotation).
    """
    # Matches: theme = rx.Cookie(...)  OR  theme: str = rx.Cookie(...)
    pattern = re.compile(
        r"\btheme\s*(?::\s*[A-Za-z_][\w\.\[\]\, ]*)?\s*=\s*rx\.Cookie\s*\("
    )
    matches = [p for p, c in python_sources.items() if pattern.search(c)]
    assert matches, (
        "Could not find a state field named `theme` assigned to `rx.Cookie(...)` "
        f"in any Python source under {PROJECT_DIR}."
    )


def test_toggle_uses_exactly_light_and_dark(python_sources):
    """
    The project's Python sources must reference both string literals "light"
    and "dark" (the two values the toggle switches between).
    """
    has_light = False
    has_dark = False
    light_pat = re.compile(r"[\"']light[\"']")
    dark_pat = re.compile(r"[\"']dark[\"']")
    for content in python_sources.values():
        if light_pat.search(content):
            has_light = True
        if dark_pat.search(content):
            has_dark = True
        if has_light and has_dark:
            break
    assert has_light, (
        'Expected the string literal "light" to appear in the project sources '
        "as one of the two theme values."
    )
    assert has_dark, (
        'Expected the string literal "dark" to appear in the project sources '
        "as the toggled theme value."
    )


def test_button_label_in_python_sources(python_sources):
    """
    The button label `Toggle Theme` must appear in the project's Python
    sources (it is what the page renders inside `rx.button(...)`).
    """
    found = any("Toggle Theme" in content for content in python_sources.values())
    assert found, (
        'Expected the string "Toggle Theme" to appear in the project sources '
        "as the button label."
    )


def test_frontend_export_succeeds_and_creates_web_dir(export_frontend):
    """`uv run reflex export --frontend-only --no-zip` must succeed and create `.web/`."""
    assert os.path.isdir(export_frontend), (
        f"Expected exported frontend directory at {export_frontend}."
    )


def test_exported_frontend_contains_button_label(export_frontend):
    """The exported frontend must contain the visible button label."""
    needle = "Toggle Theme"
    for path in _iter_exported_frontend_files(export_frontend):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                if needle in f.read():
                    return
        except OSError:
            continue
    pytest.fail(
        f'Could not find the button label "{needle}" in any file under '
        f"{export_frontend}. The frontend export does not appear to wire up "
        "the Toggle Theme button."
    )


def test_exported_frontend_binds_theme_cookie(export_frontend):
    """
    The exported frontend must reference either the cookie name `app_theme`
    or the state variable name `theme`, indicating the cookie-backed state
    is wired into the page.
    """
    found_app_theme = False
    found_theme_var = False
    theme_word = re.compile(r"\btheme\b")
    for path in _iter_exported_frontend_files(export_frontend):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        if "app_theme" in content:
            found_app_theme = True
        if theme_word.search(content):
            found_theme_var = True
        if found_app_theme and found_theme_var:
            break

    assert found_app_theme or found_theme_var, (
        "Could not find either the cookie name 'app_theme' or the state "
        "variable 'theme' anywhere in the exported frontend output under "
        f"{export_frontend}. The cookie-backed theme state does not appear to "
        "be wired into the page."
    )
