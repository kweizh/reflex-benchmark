import os
import shutil
import subprocess


def test_python3_available():
    assert shutil.which("python3") is not None, "python3 is not available in PATH."


def test_uv_available():
    uv_path = shutil.which("uv")
    assert uv_path is not None, "uv package manager is not available in PATH."
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"`uv --version` failed (returncode={result.returncode}). "
        f"stderr: {result.stderr}"
    )


def test_home_user_directory_exists():
    assert os.path.isdir("/home/user"), "/home/user directory does not exist."
