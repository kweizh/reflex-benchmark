import os
import shutil


HOME_DIR = "/home/user"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH. The Reflex project relies on uv "
        "for Python environment management."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH. The verifier uses the system "
        "python3 to drive subprocess-based checks."
    )


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), (
        f"Home directory {HOME_DIR} does not exist; the task expects the "
        "project to be created under this path."
    )
