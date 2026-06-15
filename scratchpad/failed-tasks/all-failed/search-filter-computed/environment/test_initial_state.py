import os
import shutil
import subprocess


PROJECT_DIR = "/home/user/myproject"


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "uv binary not found in PATH. Reflex tasks rely on uv to manage the Python environment."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH. The verifier runs with system python3."
    )


def test_curl_binary_available():
    assert shutil.which("curl") is not None, (
        "curl binary not found in PATH. The verifier uses curl to probe the Reflex server."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected pre-existing Reflex project directory at {PROJECT_DIR}."
    )


def test_pyproject_toml_exists():
    pyproject_path = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject_path), (
        f"Expected pyproject.toml at {pyproject_path} from the `uv init` + `uv add reflex` scaffold."
    )


def test_pyproject_declares_reflex_dependency():
    pyproject_path = os.path.join(PROJECT_DIR, "pyproject.toml")
    with open(pyproject_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "reflex" in content.lower(), (
        f"Expected `reflex` to be listed as a dependency in {pyproject_path}."
    )


def test_rxconfig_exists():
    rxconfig_path = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig_path), (
        f"Expected rxconfig.py at {rxconfig_path}; this is created by `reflex init --template blank`."
    )


def test_app_module_exists():
    app_module_path = os.path.join(PROJECT_DIR, "myproject", "myproject.py")
    assert os.path.isfile(app_module_path), (
        f"Expected the Reflex app entry module at {app_module_path}."
    )


def test_uv_can_resolve_reflex_in_project():
    # Confirm the Reflex package is actually installed inside the uv-managed
    # environment of the scaffolded project. We deliberately do NOT `import reflex`
    # in the system interpreter (it is not installed there) -- instead we exercise
    # the uv-managed virtualenv that the task uses at runtime.
    result = subprocess.run(
        ["uv", "run", "python", "-c", "import reflex; print(reflex.__version__)"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        "Expected `uv run python -c 'import reflex'` to succeed in the scaffolded project. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
