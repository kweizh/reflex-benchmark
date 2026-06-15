import os
import shutil


PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The `uv` binary is required to manage the Reflex project but was not found in PATH."
    )


def test_node_binary_available():
    assert shutil.which("node") is not None, (
        "Node.js is required by Reflex to build the frontend but `node` was not found in PATH."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected the empty Reflex project directory `{PROJECT_DIR}` to exist before the task starts."
    )
