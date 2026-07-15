import os
import shutil


HOME_DIR = "/home/user"


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager was not found in PATH. It is required to manage "
        "the Reflex Python environment."
    )


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."
