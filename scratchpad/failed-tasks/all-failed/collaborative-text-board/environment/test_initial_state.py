import os
import shutil


HOME_DIR = "/home/user"


def test_home_dir_exists() -> None:
    assert os.path.isdir(HOME_DIR), f"Expected home directory {HOME_DIR} to exist."


def test_python3_available() -> None:
    assert shutil.which("python3") is not None, (
        "System python3 must be available on PATH for the verifier to run."
    )


def test_uv_available() -> None:
    assert shutil.which("uv") is not None, (
        "uv (Astral package manager) must be available on PATH so the project can be "
        "initialized with `uv init` / `uv add reflex` / `uv run reflex ...`."
    )


def test_project_dir_not_present_initially() -> None:
    # The executor is expected to create this project from scratch; it must NOT
    # already exist in the initial environment.
    project_dir = os.path.join(HOME_DIR, "collab_board")
    assert not os.path.exists(project_dir), (
        f"Project directory {project_dir} should not exist in the initial state; "
        "the executor is expected to create it."
    )


def test_no_reflex_process_running_initially() -> None:
    # There should be no leftover Reflex frontend/backend processes occupying the
    # default Reflex ports before the executor starts.
    import socket

    for port in (3000, 8000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex(("127.0.0.1", port))
            assert result != 0, (
                f"Port {port} appears to be in use in the initial environment; "
                "no Reflex (or other) server should be running before evaluation."
            )
