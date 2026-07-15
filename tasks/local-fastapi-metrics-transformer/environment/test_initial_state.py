import os
import shutil

PROJECT_DIR = "/home/user/metrics_app"


def test_uv_available():
    assert shutil.which("uv") is not None, "The 'uv' package manager was not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_pyproject_exists():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), f"Expected {pyproject} to exist (project should be initialized with uv)."


def test_reflex_is_a_dependency():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    with open(pyproject) as f:
        content = f.read()
    assert "reflex" in content, "Expected 'reflex' to be listed as a dependency in pyproject.toml."


def test_reflex_config_exists():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), (
        f"Expected {rxconfig} to exist (project should be initialized with the Reflex blank template)."
    )
