import os
import shutil

HOME_DIR = "/home/user"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_available():
    # The task requires managing the Python environment with the `uv` package manager.
    assert shutil.which("uv") is not None, "The `uv` package manager was not found in PATH."


def test_python3_available():
    # Initial/final state tests are executed with the system python3 interpreter.
    assert shutil.which("python3") is not None, "python3 was not found in PATH."
