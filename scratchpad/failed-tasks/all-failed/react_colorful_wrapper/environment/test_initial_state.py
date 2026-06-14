import os
import shutil
import subprocess


PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, "uv binary not found in PATH; the Reflex environment requires uv."


def test_python3_binary_available():
    assert shutil.which("python3") is not None, "python3 binary not found in PATH."


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_pyproject_toml_exists():
    pyproject_path = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject_path), f"{pyproject_path} does not exist; Reflex project not initialized."


def test_pyproject_lists_reflex_dependency():
    pyproject_path = os.path.join(PROJECT_DIR, "pyproject.toml")
    with open(pyproject_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "reflex" in content.lower(), (
        f"pyproject.toml at {pyproject_path} does not reference the 'reflex' dependency."
    )


def test_reflex_app_source_exists():
    # Reflex's blank template creates a package directory matching the project name
    # with a python module of the same name (e.g. myproject/myproject.py).
    assert os.path.isdir(PROJECT_DIR), f"{PROJECT_DIR} missing."
    found_app_module = False
    for entry in os.listdir(PROJECT_DIR):
        sub = os.path.join(PROJECT_DIR, entry)
        if os.path.isdir(sub):
            for candidate in os.listdir(sub):
                if candidate.endswith(".py"):
                    found_app_module = True
                    break
        if found_app_module:
            break
    assert found_app_module, (
        f"Could not find any Python source file under a package directory in {PROJECT_DIR}; "
        "Reflex blank template app module appears to be missing."
    )


def test_rxconfig_exists():
    rxconfig_path = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig_path), (
        f"{rxconfig_path} does not exist; Reflex project was not initialized with `reflex init`."
    )


def test_uv_can_resolve_reflex():
    # The Reflex CLI should be runnable through `uv run` inside the project.
    result = subprocess.run(
        ["uv", "run", "reflex", "--version"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"`uv run reflex --version` failed in {PROJECT_DIR}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
