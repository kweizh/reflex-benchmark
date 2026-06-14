"""Initial state checks for the collaborative_drawing_canvas task.

The executor will create the Reflex project from scratch under
/home/user/myproject using `uv`. We only verify that the required toolchain
is available in the container and that the project directory has been
prepared (empty) for the executor.
"""

import os
import shutil
import subprocess


PROJECT_DIR = "/home/user/myproject"


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 is required but was not found in PATH."
    )


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "uv is required to manage the Reflex project but was not found in PATH."
    )


def test_uv_version_runs():
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`uv --version` failed (returncode={result.returncode}): {result.stderr.strip()}"
    )


def test_project_dir_exists_and_is_empty():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to be pre-created (empty)."
    )
    entries = [
        e
        for e in os.listdir(PROJECT_DIR)
        if not e.startswith(".keep")
    ]
    assert entries == [], (
        f"Expected {PROJECT_DIR} to be empty before evaluation, but found: {entries}"
    )


def test_no_stale_backend_on_port_8000():
    # Best-effort: confirm port 8000 is not already bound by a leftover process.
    # Use python stdlib so we don't rely on extra OS tools.
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(("127.0.0.1", 8000))
    finally:
        sock.close()
    assert result != 0, (
        "Port 8000 is already in use before evaluation; expected it to be free."
    )
