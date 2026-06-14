"""Initial-state checks for the live_stock_ticker_sse task.

These run under the system python3 BEFORE the executor starts the task.
They only validate that the base environment is sane (uv available,
python3 available, home directory exists). They MUST NOT assert that the
project that the executor is supposed to create already exists.
"""

import os
import shutil
import socket


HOME_DIR = "/home/user"
PROJECT_DIR = "/home/user/ticker_app"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_binary_available():
    # The research plan requires using `uv` to manage the Python env for Reflex,
    # because reflex's dependencies can conflict with the system Python.
    assert shutil.which("uv") is not None, (
        "`uv` binary not found in PATH. The task environment must provide uv "
        "(see https://docs.astral.sh/uv/) so the executor can manage the "
        "Reflex Python environment."
    )


def test_system_python3_available():
    # The harbor verifier runs final-state tests with the system python3.
    assert shutil.which("python3") is not None, (
        "`python3` not found in PATH. The system python3 interpreter is "
        "required to run the verification tests."
    )


def test_project_dir_not_yet_created():
    # The executor is responsible for creating the project directory.
    # We assert it does NOT exist yet so that we know we're in a clean state.
    assert not os.path.exists(PROJECT_DIR), (
        f"Unexpected pre-existing project at {PROJECT_DIR}; the executor "
        f"is supposed to create this directory from scratch."
    )


def test_backend_port_8000_is_free():
    # Verification will start a reflex backend on port 8000. Make sure nothing
    # is already bound to that port at the initial state.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", 8000))
    finally:
        sock.close()
    assert result != 0, (
        "Port 8000 on localhost is already in use at initial state; the "
        "Reflex backend used by verification needs this port free."
    )
