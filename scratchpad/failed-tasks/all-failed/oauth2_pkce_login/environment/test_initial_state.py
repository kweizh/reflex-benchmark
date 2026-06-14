import os
import shutil
import subprocess


def test_uv_binary_available():
    """uv must be available so the executor can manage the Python env per plan.md."""
    assert shutil.which("uv") is not None, "uv binary not found in PATH."


def test_python3_available():
    """System python3 must be available; verifier tests run with system python3."""
    assert shutil.which("python3") is not None, "python3 binary not found in PATH."


def test_python3_version():
    """Sanity check that the system python is recent enough to run the verifier."""
    result = subprocess.run(
        ["python3", "--version"], capture_output=True, text=True, check=True
    )
    out = (result.stdout + result.stderr).strip()
    assert out.startswith("Python 3."), (
        f"Expected 'Python 3.x' from `python3 --version`, got: {out!r}"
    )


def test_httpx_importable_for_verifier():
    """The verifier uses httpx to drive HTTP-level checks; it must be importable."""
    result = subprocess.run(
        ["python3", "-c", "import httpx"], capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"`python3 -c 'import httpx'` failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )


def test_home_user_exists():
    """/home/user is the canonical home directory used by all generated paths."""
    assert os.path.isdir("/home/user"), "/home/user directory does not exist."
