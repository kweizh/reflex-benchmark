import os
import shutil


HOME_DIR = "/home/user"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; the executor needs uv to manage the Reflex project."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH; required for verification scripts and reflex."
    )


def test_curl_binary_available():
    assert shutil.which("curl") is not None, (
        "curl binary not found in PATH; useful for diagnosing the reflex server."
    )
