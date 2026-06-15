"""Initial state checks for the wrap-react-colorful task.

The executor will create the Reflex application inside /home/user/myproject.
These tests only verify that the environment is ready: the working directory
exists, system python3 is available, and `uv` is available to manage the
Reflex environment as required by plan.md.
"""

import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/myproject"


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before evaluation."
    )


def test_system_python3_available():
    assert shutil.which("python3") is not None, (
        "system python3 is required for verification scripts but was not found in PATH."
    )


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "`uv` package manager is required (per plan.md) to manage the Reflex environment."
    )


def test_uv_runs():
    result = subprocess.run(
        ["uv", "--version"], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, (
        f"`uv --version` failed with stderr: {result.stderr.strip()!r}"
    )


def test_node_available():
    # Reflex's frontend export step requires Node.js to be available so that
    # the npm install / next build pipeline can pull `react-colorful`.
    assert shutil.which("node") is not None, (
        "node binary not found in PATH; required by `reflex export --frontend-only`."
    )
