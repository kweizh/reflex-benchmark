import os
import shutil
import socket


HOME_DIR = "/home/user"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Expected home directory {HOME_DIR} to exist."


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The `uv` binary must be available on PATH for the agent to manage the Reflex project's Python environment."
    )


def test_node_binary_available():
    assert shutil.which("node") is not None, (
        "Reflex requires Node.js to compile the frontend; `node` must be available on PATH."
    )


def test_npm_binary_available():
    assert shutil.which("npm") is not None, (
        "Reflex requires npm to install frontend dependencies; `npm` must be available on PATH."
    )


def test_system_python3_available():
    assert shutil.which("python3") is not None, (
        "The verifier relies on the system `python3` interpreter."
    )


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def test_port_3000_is_free():
    assert _port_is_free(3000), (
        "TCP port 3000 must be free before the task starts (Reflex frontend default)."
    )


def test_port_8000_is_free():
    assert _port_is_free(8000), (
        "TCP port 8000 must be free before the task starts (Reflex backend default)."
    )
