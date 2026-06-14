import os
import shutil

HOME_DIR = "/home/user"
PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; the Reflex environment requires uv to manage the Python project."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH; verifier tests rely on the system python3 interpreter."
    )


def test_pytest_available():
    assert shutil.which("pytest") is not None, (
        "pytest binary not found in PATH; verifier tests are executed via pytest."
    )


def test_home_user_directory_exists():
    assert os.path.isdir(HOME_DIR), (
        f"Home directory {HOME_DIR} is missing; the task workspace must be available before the executor starts."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} is missing; the executor expects this exact path to exist before they start working."
    )


def test_project_dir_is_initially_empty():
    contents = os.listdir(PROJECT_DIR)
    assert contents == [], (
        f"Project directory {PROJECT_DIR} must start empty so the executor initializes the Reflex project themselves; found: {contents}"
    )
