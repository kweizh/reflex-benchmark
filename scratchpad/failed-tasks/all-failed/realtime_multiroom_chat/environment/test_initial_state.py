import os
import shutil
import subprocess


def test_home_directory_exists():
    assert os.path.isdir("/home/user"), "/home/user home directory does not exist."


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The `uv` Python package manager binary must be installed in PATH per the project plan."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "`python3` binary is required for the verifier and must be present in PATH."
    )


def test_sqlite3_binary_available():
    assert shutil.which("sqlite3") is not None, (
        "`sqlite3` CLI is required for inspecting the SQLite database during verification."
    )


def test_curl_binary_available():
    assert shutil.which("curl") is not None, (
        "`curl` is required for hitting the Reflex backend during verification."
    )


def test_uv_runs():
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`uv --version` failed with code {result.returncode}: stderr={result.stderr!r}"
    )
