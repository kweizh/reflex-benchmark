import os
import shutil

PROJECT_DIR = "/home/user/shopping_cart"
APP_PACKAGE_DIR = os.path.join(PROJECT_DIR, "shopping_cart")


def test_uv_binary_available():
    assert shutil.which("uv") is not None, "The 'uv' package manager was not found in PATH."


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_rxconfig_exists():
    config_path = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(config_path), (
        f"Expected a blank Reflex project with {config_path} present."
    )


def test_pyproject_declares_reflex():
    pyproject_path = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject_path), f"Expected {pyproject_path} to exist."
    with open(pyproject_path) as f:
        content = f.read()
    assert "reflex" in content, "Expected 'reflex' to be declared as a dependency in pyproject.toml."


def test_app_package_directory_exists():
    assert os.path.isdir(APP_PACKAGE_DIR), (
        f"Expected the Reflex app package directory {APP_PACKAGE_DIR} to exist."
    )


def test_virtualenv_installed():
    venv_dir = os.path.join(PROJECT_DIR, ".venv")
    assert os.path.isdir(venv_dir), (
        f"Expected the uv-managed virtual environment {venv_dir} with dependencies installed."
    )
