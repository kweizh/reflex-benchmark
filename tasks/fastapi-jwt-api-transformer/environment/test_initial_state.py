import os
import shutil


PROJECT_DIR = "/home/user/myapp"


def test_python3_available():
    assert shutil.which("python3") is not None, "python3 is not available in PATH."


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH. Reflex requires uv to manage its Python environment."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )
