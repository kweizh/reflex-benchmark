import os
import shutil


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; uv is required to manage the Reflex environment."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH; the verification harness depends on system python3."
    )


def test_home_user_directory_exists():
    assert os.path.isdir("/home/user"), (
        "/home/user directory must exist as the working directory for the task."
    )
