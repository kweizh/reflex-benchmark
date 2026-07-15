import os
import shutil

PROJECT_DIR = "/home/user/approval_app"


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager is required to manage the Reflex environment "
        "but was not found in PATH."
    )


def test_node_available():
    assert shutil.which("node") is not None, (
        "Node.js is required by the Reflex frontend but was not found in PATH."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"The project directory {PROJECT_DIR} does not exist."
    )
