import os
import shutil


PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' binary was not found on PATH. The Reflex evaluation environment "
        "requires the Astral 'uv' Python project manager."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "System 'python3' is required to run initial- and final-state tests."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected the project workspace at {PROJECT_DIR} to exist before the task begins."
    )


def test_project_dir_is_empty_or_minimal():
    # The project directory should exist but should NOT already contain a Reflex
    # app source file or rxconfig.py. The executor is responsible for creating those.
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert not os.path.exists(rxconfig), (
        f"Did not expect {rxconfig} to exist before the task begins; "
        "the executor must create the Reflex project."
    )
