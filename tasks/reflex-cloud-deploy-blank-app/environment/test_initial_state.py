import os
import shutil


def test_python3_available():
    assert shutil.which("python3") is not None, "python3 binary not found in PATH."


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH; uv is required to manage the Reflex project's Python environment."
    )


def test_home_user_directory_exists():
    assert os.path.isdir("/home/user"), "Home directory /home/user does not exist."


def test_reflex_cloud_token_env_set():
    token = os.environ.get("REFLEX_CLOUD_TOKEN", "")
    assert token, (
        "REFLEX_CLOUD_TOKEN environment variable is not set; it is required to authenticate with Reflex Cloud."
    )


def test_reflex_cloud_project_id_env_set():
    project_id = os.environ.get("REFLEX_CLOUD_PROJECT_ID", "")
    assert project_id, (
        "REFLEX_CLOUD_PROJECT_ID environment variable is not set; it is required to target a Reflex Cloud project."
    )
