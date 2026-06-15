import os
import shutil


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH. The task requires the uv package manager "
        "to manage the Reflex Python environment."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH. The verifier uses system python3 "
        "to run final-state tests."
    )


def test_home_user_directory_exists():
    assert os.path.isdir("/home/user"), (
        "/home/user directory does not exist. The task expects this as the "
        "base directory for the Reflex project."
    )
