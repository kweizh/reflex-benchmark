import os
import shutil

PROJECT_DIR = "/home/user/registration_wizard"


def test_uv_available():
    assert shutil.which("uv") is not None, "The 'uv' package manager was not found in PATH."


def test_python3_available():
    assert shutil.which("python3") is not None, "python3 was not found in PATH."


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."
