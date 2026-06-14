import os
import shutil
import socket
import subprocess

HOME = "/home/user"
PROJECT_DIR = "/home/user/numpy_chart_serializer"


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
        except (ConnectionRefusedError, socket.timeout, OSError):
            return True
        return False


def test_home_directory_exists():
    assert os.path.isdir(HOME), f"Expected home directory {HOME} to exist."


def test_uv_available_in_path():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH. The research plan requires uv to manage the Reflex environment."
    )


def test_uv_runs():
    result = subprocess.run(
        ["uv", "--version"], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, (
        f"`uv --version` failed (returncode={result.returncode}): stderr={result.stderr!r}"
    )
    assert "uv" in (result.stdout + result.stderr).lower(), (
        f"`uv --version` produced unexpected output: {result.stdout!r}"
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH; the verifier needs system python3."
    )


def test_project_directory_not_yet_created():
    # The executor is expected to create the project from scratch.
    # If something is already there, evaluation results would be unreliable.
    assert not os.path.exists(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} must NOT exist before evaluation begins; the executor creates it."
    )


def test_backend_port_8000_is_free():
    assert _port_is_free(8000), (
        "Port 8000 must be free before evaluation; a leftover Reflex backend appears to be running."
    )


def test_frontend_port_3000_is_free():
    assert _port_is_free(3000), (
        "Port 3000 must be free before evaluation; a leftover Reflex frontend appears to be running."
    )
