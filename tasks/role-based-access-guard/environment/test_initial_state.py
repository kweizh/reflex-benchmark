import os
import shutil

HOME_DIR = "/home/user"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager binary was not found in PATH. "
        "It is required to manage the Python environment for this task."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 was not found in PATH."
    )
