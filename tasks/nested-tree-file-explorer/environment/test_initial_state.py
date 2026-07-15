import os
import shutil

HOME_DIR = "/home/user"


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager is required to manage the Reflex project "
        "but was not found in PATH."
    )


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 is required to run the verification tests but was not found in PATH."
    )
