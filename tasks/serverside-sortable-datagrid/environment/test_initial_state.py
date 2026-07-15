import shutil
import subprocess


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager is required to manage the Python environment "
        "but was not found in PATH."
    )


def test_uv_runs():
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"'uv --version' failed with exit code {result.returncode}. "
        f"stderr: {result.stderr}"
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 is required to run the verification tests but was not found in PATH."
    )
