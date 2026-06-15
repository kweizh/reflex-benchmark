import os
import shutil
import subprocess


HOME_DIR = "/home/user"


def test_home_dir_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' binary is required to manage the Reflex Python environment "
        "but was not found on PATH."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "System python3 is required by the verifier and was not found on PATH."
    )


def test_uv_runs():
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`uv --version` failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "uv" in result.stdout.lower(), (
        f"`uv --version` output did not look like uv: {result.stdout!r}"
    )
