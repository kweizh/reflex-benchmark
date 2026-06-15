import os
import shutil
import subprocess

HOME_DIR = "/home/user"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_python3_available():
    python3 = shutil.which("python3")
    assert python3 is not None, "python3 binary not found in PATH."


def test_uv_binary_available():
    uv_bin = shutil.which("uv")
    assert uv_bin is not None, (
        "uv binary not found in PATH. Reflex requires uv to manage its Python "
        "environment because some of its dependencies conflict with system "
        "Python packages."
    )


def test_uv_is_runnable():
    uv_bin = shutil.which("uv")
    assert uv_bin is not None, "uv binary not found in PATH."
    result = subprocess.run(
        [uv_bin, "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`uv --version` failed with exit code {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "uv" in result.stdout.lower(), (
        f"Unexpected output from `uv --version`: {result.stdout!r}"
    )


def test_curl_available():
    # curl is used by the final-state verifier to probe the running Reflex dev server.
    assert shutil.which("curl") is not None, "curl binary not found in PATH."
