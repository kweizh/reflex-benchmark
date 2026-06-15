import os
import shutil


PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; required to manage the Reflex Python environment."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH; the verifier uses the system python3."
    )


def test_sqlite3_binary_available():
    assert shutil.which("sqlite3") is not None, (
        "sqlite3 binary not found in PATH; required to inspect the generated SQLite database."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the executor starts."
    )
