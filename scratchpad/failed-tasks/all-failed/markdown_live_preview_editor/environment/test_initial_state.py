import os
import shutil
import subprocess


HOME_DIR = "/home/user"
PROJECT_DIR = "/home/user/myproject"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_binary_available():
    uv_path = shutil.which("uv")
    assert uv_path is not None, "uv binary not found in PATH; required to manage the Reflex Python environment."


def test_uv_runs():
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"`uv --version` exited with non-zero status (stderr: {result.stderr.strip()})."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, "python3 binary not found in PATH."


def test_node_available():
    # Reflex compiles a Next.js frontend, which requires Node.js to be present.
    assert shutil.which("node") is not None, (
        "node binary not found in PATH; required to compile and serve the Reflex frontend."
    )


def test_project_dir_not_yet_initialized():
    # The executor is responsible for creating the project directory and initializing
    # the Reflex application. If a project already exists from a prior incomplete run,
    # we only assert that it is not blocking creation by being a non-directory file.
    if os.path.exists(PROJECT_DIR):
        assert os.path.isdir(PROJECT_DIR), (
            f"{PROJECT_DIR} exists but is not a directory; cannot host the Reflex project."
        )
