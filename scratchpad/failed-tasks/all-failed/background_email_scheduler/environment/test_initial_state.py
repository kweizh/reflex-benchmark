import os
import shutil


HOME_DIR = "/home/user"
PROJECT_DIR = "/home/user/email_scheduler"


def test_home_dir_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; the task environment must ship the Astral uv "
        "package manager so the agent can manage the Reflex project."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH; required to run the verifier scripts."
    )


def test_pkill_available():
    assert shutil.which("pkill") is not None, (
        "pkill binary not found in PATH; required to tear down background Reflex servers."
    )


def test_node_available():
    assert shutil.which("node") is not None, (
        "node binary not found in PATH; `reflex init --template blank` bootstraps a "
        "Next.js frontend at project creation time and needs Node available."
    )


def test_project_directory_absent_initially():
    # The executor is expected to create the project from scratch using `uv init` and
    # `uv run reflex init --template blank`. The directory must NOT pre-exist so that
    # the verifier can later assert the executor produced the expected files.
    assert not os.path.exists(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} must not exist before the task starts; "
        f"the executor is responsible for creating it."
    )
