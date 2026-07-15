import os
import shutil


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager must be installed and available in PATH; "
        "it is required to manage the Reflex Python environment."
    )


def test_home_directory_exists():
    assert os.path.isdir("/home/user"), (
        "The home directory /home/user must exist as the base for the project."
    )
