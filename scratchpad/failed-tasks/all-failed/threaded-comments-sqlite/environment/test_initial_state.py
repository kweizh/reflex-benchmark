import os
import shutil

PROJECT_DIR = "/home/user/threaded_comments"


def test_uv_available():
    assert shutil.which("uv") is not None, "uv binary not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_pyproject_exists():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), (
        f"Expected uv project file {pyproject} to exist (project not initialized)."
    )


def test_reflex_scaffold_exists():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), (
        f"Expected Reflex config {rxconfig} to exist (reflex init not run)."
    )
