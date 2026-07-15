import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/note_app"


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager must be installed and available in PATH."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_pyproject_exists():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), (
        f"Expected an initialized uv project with {pyproject}."
    )


def test_reflex_declared_as_dependency():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    with open(pyproject) as f:
        content = f.read()
    assert "reflex" in content, (
        "reflex should already be added as a project dependency in pyproject.toml."
    )


def test_reflex_config_exists():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), (
        f"Expected a Reflex project config at {rxconfig} (created by 'reflex init')."
    )


def test_reflex_runnable_via_uv():
    result = subprocess.run(
        ["uv", "run", "reflex", "--help"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Expected 'uv run reflex --help' to succeed in the project directory, "
        f"but it failed: {result.stdout}\n{result.stderr}"
    )
