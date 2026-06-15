import os
import re
import shutil
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/myproject"
WEB_DIR = os.path.join(PROJECT_DIR, ".web")
FRONTEND_PORT = 3000
BACKEND_PORT = 8000

EXCLUDED_DIRS = {".web", ".venv", "venv", "__pycache__", ".git", "node_modules"}


def _kill_leftover_servers():
    """Best-effort kill of any leftover server holding ports 3000 or 8000."""
    for port in (FRONTEND_PORT, BACKEND_PORT):
        try:
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            # fuser may not be installed; ignore.
            pass
        except subprocess.TimeoutExpired:
            pass
    time.sleep(1)


def _iter_python_sources(root):
    """Yield (path, content) for every .py file under `root` excluding common build/venv dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            full_path = os.path.join(dirpath, filename)
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                    yield full_path, fh.read()
            except OSError:
                continue


@pytest.fixture(scope="session", autouse=True)
def _cleanup_servers():
    """Kill any leftover dev servers before and after the test session."""
    _kill_leftover_servers()
    yield
    _kill_leftover_servers()


@pytest.fixture(scope="session")
def python_sources():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist; the executor was expected to initialize the Reflex project there."
    )
    sources = list(_iter_python_sources(PROJECT_DIR))
    assert sources, (
        f"No Python source files were found under {PROJECT_DIR}; the executor must create a Reflex application."
    )
    return sources


@pytest.fixture(scope="session")
def compiled_frontend():
    """Compile the Reflex frontend via `uv run reflex export --frontend-only --no-zip`.

    Returns the absolute path to the .web directory that contains the compiled output.
    """
    assert shutil.which("uv") is not None, "uv binary not found in PATH; cannot compile Reflex frontend."

    # Remove any pre-existing compiled artifacts so the export step recompiles from source.
    if os.path.isdir(WEB_DIR):
        shutil.rmtree(WEB_DIR, ignore_errors=True)

    env = os.environ.copy()
    # Make sure reflex does not attempt to open a browser or block on interactive prompts.
    env.setdefault("REFLEX_TELEMETRY_ENABLED", "false")

    result = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=900,
    )

    # Always try to kill any servers reflex might have started during the export.
    _kill_leftover_servers()

    assert result.returncode == 0, (
        "Failed to run `uv run reflex export --frontend-only --no-zip` in "
        f"{PROJECT_DIR}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert os.path.isdir(WEB_DIR), (
        f"Expected the compiled frontend directory {WEB_DIR} to exist after `reflex export`, "
        f"but it was not created.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return WEB_DIR


def test_source_uses_rx_cond_with_show_panel(python_sources):
    """Criterion 1: AST/regex search finds rx.cond( referencing a state var named show_panel."""
    # Match rx.cond(<something>.show_panel ...) — the first argument should reference a state attr `show_panel`.
    pattern = re.compile(
        r"rx\.cond\s*\(\s*[A-Za-z_][\w.]*\.show_panel\b",
        re.MULTILINE,
    )
    matches = []
    for path, content in python_sources:
        if pattern.search(content):
            matches.append(path)
    assert matches, (
        "Could not find any `rx.cond(<State>.show_panel ...)` call in the project's Python sources. "
        "The index page must conditionally render the panel via `rx.cond` against the `show_panel` state var."
    )


def test_boolean_state_var_show_panel_defaults_false(python_sources):
    """Criterion 2: A boolean state var `show_panel: bool = False` is declared on an rx.State subclass."""
    # Find each class definition that inherits from rx.State (directly or via attribute access).
    class_pattern = re.compile(
        r"class\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*:",
        re.MULTILINE,
    )
    # Within that class body, look for `show_panel : bool = False` (whitespace tolerant).
    show_panel_pattern = re.compile(
        r"^\s*show_panel\s*:\s*bool\s*=\s*False\b",
        re.MULTILINE,
    )

    found = False
    for path, content in python_sources:
        for match in class_pattern.finditer(content):
            bases = match.group(2)
            if "rx.State" not in bases and "State" not in bases.split(","):
                # Conservative: require the literal text "rx.State" or a bare "State" base.
                # We still continue; rx.State subclassing is what we expect from the docs.
                if "rx.State" not in bases:
                    continue
            # Extract the body of the class by slicing until the next top-level def/class
            # at the same indentation. A simple heuristic is enough for static regex checks.
            body_start = match.end()
            body = content[body_start:]
            # Cut the body at the next class definition that starts at column 0.
            next_class = re.search(r"\nclass\s+\w+\s*\(", body)
            if next_class:
                body = body[: next_class.start()]
            if show_panel_pattern.search(body):
                found = True
                break
        if found:
            break

    assert found, (
        "Could not find a boolean state var declaration `show_panel: bool = False` inside any class "
        "that inherits from `rx.State`. The state must define a default-False boolean named `show_panel`."
    )


def test_cached_computed_var_visibility_label(python_sources):
    """Criterion 3: A cached computed var `visibility_label` returns the two visibility literals."""
    # Match `@rx.var(... cache=True ...)` on the line(s) directly above `def visibility_label(...)`.
    # Allow other decorators / whitespace between them, but keep the search reasonably tight.
    decorator_def_pattern = re.compile(
        r"@rx\.var\s*\(\s*[^)]*\bcache\s*=\s*True\b[^)]*\)\s*(?:\r?\n\s*@[^\n]*)*\s*\r?\n\s*def\s+visibility_label\s*\(\s*self\s*\)\s*(?:->\s*[^:]+)?:\s*\r?\n(?P<body>(?:[ \t]+[^\n]*\r?\n)+)",
        re.MULTILINE,
    )

    found_decorator_and_def = False
    found_shown_literal = False
    found_hidden_literal = False

    for path, content in python_sources:
        for match in decorator_def_pattern.finditer(content):
            found_decorator_and_def = True
            body = match.group("body")
            if "Visibility: shown" in body:
                found_shown_literal = True
            if "Visibility: hidden" in body:
                found_hidden_literal = True
            if found_shown_literal and found_hidden_literal:
                break
        if found_shown_literal and found_hidden_literal:
            break

    assert found_decorator_and_def, (
        "Could not find a `@rx.var(cache=True)`-decorated method named `visibility_label(self)` "
        "in the project's Python sources. The state must expose a cached computed var named `visibility_label`."
    )
    assert found_shown_literal, (
        'The `visibility_label` computed var body must contain the literal string "Visibility: shown".'
    )
    assert found_hidden_literal, (
        'The `visibility_label` computed var body must contain the literal string "Visibility: hidden".'
    )


def test_compiled_frontend_contains_required_literals(compiled_frontend):
    """Criterion 4: After exporting the frontend, the compiled output contains all three literals."""
    required_literals = [
        "Secret Panel Content",
        "Visibility: shown",
        "Visibility: hidden",
    ]
    found = {literal: False for literal in required_literals}

    for dirpath, _dirnames, filenames in os.walk(compiled_frontend):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    contents = fh.read()
            except OSError:
                continue
            for literal in required_literals:
                if not found[literal] and literal in contents:
                    found[literal] = True
            if all(found.values()):
                break
        if all(found.values()):
            break

    missing = [literal for literal, was_found in found.items() if not was_found]
    assert not missing, (
        "The compiled Reflex frontend under "
        f"{compiled_frontend} is missing the following expected literal(s): {missing}. "
        "Ensure the `/` page renders `Secret Panel Content` inside the `rx.cond` panel and "
        'displays the `visibility_label` text ("Visibility: shown" / "Visibility: hidden").'
    )
