import os
import shutil
import subprocess

HOME_DIR = "/home/user"
PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The `uv` binary must be installed and available on PATH "
        "to manage the Reflex Python environment."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "`python3` must be available on PATH for the verifier to run checks."
    )


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} must exist."


def test_project_workspace_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project workspace directory {PROJECT_DIR} must exist before the task "
        "begins so the executor can initialize the Reflex app inside it."
    )


def test_project_workspace_is_pristine():
    # The executor will initialize the Reflex app here; the workspace must not
    # already contain a Reflex project.
    rxconfig_path = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert not os.path.exists(rxconfig_path), (
        f"{rxconfig_path} must not exist at task start; the executor will create it "
        "via `uv run reflex init`."
    )


def test_uv_runs():
    # Make sure `uv` actually executes (e.g., not just a broken symlink).
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`uv --version` failed with exit code {result.returncode}. "
        f"stderr: {result.stderr!r}"
    )
    assert "uv" in result.stdout.lower(), (
        f"Unexpected output from `uv --version`: {result.stdout!r}"
    )
