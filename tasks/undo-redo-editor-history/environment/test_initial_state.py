import os
import shutil

PROJECT_DIR = "/home/user/editor"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, "uv binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_pyproject_exists_and_declares_reflex():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), f"Expected {pyproject} to exist."
    with open(pyproject) as f:
        content = f.read()
    assert "reflex" in content.lower(), "Expected reflex to be declared as a dependency in pyproject.toml."


def test_venv_installed():
    venv = os.path.join(PROJECT_DIR, ".venv")
    assert os.path.isdir(venv), f"Expected a uv-managed virtual environment at {venv}."


def test_rxconfig_exists():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), f"Expected the Reflex config {rxconfig} to exist (blank project scaffold)."
