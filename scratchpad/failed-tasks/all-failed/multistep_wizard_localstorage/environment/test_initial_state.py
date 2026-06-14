import os
import shutil


HOME_DIR = "/home/user"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' binary must be installed and available on PATH so the executor "
        "can manage the Reflex Python environment."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "The system 'python3' interpreter must be available on PATH; the verifier "
        "runs entirely under system python3 without any Reflex installation."
    )


def test_curl_binary_available():
    assert shutil.which("curl") is not None, (
        "The 'curl' binary must be available on PATH so verification can probe "
        "the Reflex frontend and backend HTTP endpoints."
    )


def test_sqlite3_binary_available():
    assert shutil.which("sqlite3") is not None, (
        "The 'sqlite3' binary must be available on PATH so verification can "
        "inspect the Reflex SQLite database file."
    )


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), (
        f"The home directory '{HOME_DIR}' must exist as the parent of the "
        "project workspace the executor will create."
    )


def test_wizard_app_directory_not_yet_created():
    project_dir = os.path.join(HOME_DIR, "wizard_app")
    assert not os.path.exists(project_dir), (
        f"The project directory '{project_dir}' must not exist before the "
        "executor starts; the executor is responsible for creating it."
    )
