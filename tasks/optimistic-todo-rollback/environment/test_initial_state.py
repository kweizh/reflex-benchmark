import os
import shutil

HOME_DIR = "/home/user"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The `uv` package manager was not found in PATH. Reflex must be managed and run through `uv`."
    )


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_sqlite3_available():
    assert shutil.which("sqlite3") is not None, (
        "The `sqlite3` CLI was not found in PATH; it is required to inspect the local SQLite database."
    )
