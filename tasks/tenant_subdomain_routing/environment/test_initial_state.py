import os
import shutil


PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' binary must be installed and available in PATH to manage the Reflex environment."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "system 'python3' must be available in PATH to run verifier checks."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} must exist before the executor starts working."
    )


def test_port_8000_is_initially_free():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        result = s.connect_ex(("127.0.0.1", 8000))
    assert result != 0, (
        "TCP port 8000 must be free at the start of the task; "
        "an existing process is already listening on it."
    )
