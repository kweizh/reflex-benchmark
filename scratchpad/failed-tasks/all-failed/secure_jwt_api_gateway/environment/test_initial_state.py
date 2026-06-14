import os
import shutil
import subprocess


HOME_DIR = "/home/user"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), (
        f"Expected home directory {HOME_DIR} to exist before the task begins."
    )


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "`uv` binary not found in PATH. The task requires `uv` to manage the "
        "Reflex Python environment (see plan.md)."
    )


def test_uv_is_runnable():
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`uv --version` exited with non-zero status: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )


def test_system_python3_available():
    assert shutil.which("python3") is not None, (
        "System `python3` not found in PATH. The final-state verifier runs "
        "with the system python3."
    )


def test_project_directory_does_not_yet_exist():
    project_path = os.path.join(HOME_DIR, "secure_jwt_api_gateway")
    assert not os.path.exists(project_path), (
        f"Project directory {project_path} must not exist before the task "
        "begins; the executor is expected to create it from scratch."
    )
