import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/sales_report"


def test_uv_available():
    assert shutil.which("uv") is not None, "The 'uv' package manager was not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_pyproject_exists():
    path = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(path), f"Expected uv project manifest at {path}."


def test_rxconfig_exists():
    path = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(path), (
        f"Expected a Reflex config at {path} (blank Reflex app should be initialized)."
    )


def test_app_package_dir_exists():
    path = os.path.join(PROJECT_DIR, "sales_report")
    assert os.path.isdir(path), (
        f"Expected the Reflex app package directory at {path}."
    )


def test_reflex_importable_in_project_env():
    result = subprocess.run(
        ["uv", "run", "python", "-c", "import reflex"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        "The 'reflex' package is not importable inside the project's uv environment. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
