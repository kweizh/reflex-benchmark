import os
import shutil
import subprocess


def test_python3_available():
    assert shutil.which("python3") is not None, "python3 binary not found in PATH."


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH. The task requires uv to manage the Reflex environment."
    )


def test_uv_version_runs():
    result = subprocess.run(
        ["uv", "--version"], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, (
        f"`uv --version` failed with exit code {result.returncode}.\nstdout={result.stdout}\nstderr={result.stderr}"
    )


def test_user_home_exists():
    assert os.path.isdir("/home/user"), (
        "/home/user directory does not exist; the task expects this to be the user's home."
    )


def test_no_pre_existing_project_dir():
    # The executor is expected to CREATE the project; the directory must not already exist
    # with a reflex project inside it.
    project_main = "/home/user/myproject/myproject/myproject.py"
    assert not os.path.isfile(project_main), (
        f"Unexpected pre-existing project file {project_main}; executor must create it."
    )
