import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/checkout_app"
APP_MODULE = os.path.join(PROJECT_DIR, "checkout_app", "checkout_app.py")


def test_uv_available():
    assert shutil.which("uv") is not None, "The 'uv' package manager was not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_pyproject_exists():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), f"Expected pyproject.toml at {pyproject} (uv-managed project)."


def test_rxconfig_exists():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), f"Expected Reflex config at {rxconfig}."


def test_app_module_exists():
    assert os.path.isfile(APP_MODULE), f"Expected pre-initialized app module at {APP_MODULE}."


def test_reflex_installed_in_project_env():
    # Reflex is NOT expected to be importable by the system python3; it lives in the
    # uv-managed project environment. Verify it is installed there via `uv run`.
    result = subprocess.run(
        ["uv", "run", "python", "-c", "import reflex; print(reflex.__version__)"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Reflex is not installed/importable in the project's uv environment. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip(), "Reflex import succeeded but reported no version string."
