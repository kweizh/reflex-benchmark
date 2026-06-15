import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/streaming_llm_panel"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; it is required to manage the Reflex Python "
        "environment for this task."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH; tests rely on the system python3."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Initial project directory {PROJECT_DIR} does not exist; the task expects "
        "an empty workspace at this path."
    )


def test_project_dir_is_empty_or_minimal():
    # The initial environment should be empty (or only contain hidden setup files
    # like a placeholder .gitkeep). The executor is expected to create the Reflex
    # project here.
    entries = [
        e for e in os.listdir(PROJECT_DIR)
        if not e.startswith(".")
    ]
    assert entries == [], (
        f"Initial project directory {PROJECT_DIR} should not contain user files "
        f"before the task begins, but found: {entries}."
    )


def test_uv_can_invoke_reflex_cli():
    # Verify uv is functional. We don't require reflex to already be installed
    # globally — the executor will add it via `uv add reflex` inside the project.
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`uv --version` failed with code {result.returncode}: {result.stderr}"
    )
