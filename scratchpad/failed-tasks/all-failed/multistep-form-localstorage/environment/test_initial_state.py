import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, "uv binary not found in PATH; it is required to manage the Reflex project."


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), f"Expected Reflex project directory at {PROJECT_DIR}."


def test_project_has_pyproject():
    pyproject_path = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject_path), f"Expected {pyproject_path} to exist for the uv-managed Reflex project."


def test_project_has_rxconfig():
    rxconfig_path = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig_path), (
        f"Expected {rxconfig_path} to exist (created by `reflex init --template blank`)."
    )


def test_reflex_available_in_project_env():
    result = subprocess.run(
        ["uv", "run", "reflex", "--help"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        "`uv run reflex --help` failed; expected Reflex to be installed in the project's uv environment.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
