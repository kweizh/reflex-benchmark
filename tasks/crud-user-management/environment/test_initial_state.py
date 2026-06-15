import os
import shutil

HOME_DIR = "/home/user"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH. The Reflex project must be managed with uv."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH. System python3 is required to run tests."
    )


def test_sqlite3_binary_available():
    assert shutil.which("sqlite3") is not None, (
        "sqlite3 binary not found in PATH. It is required to inspect the reflex.db schema."
    )


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."
