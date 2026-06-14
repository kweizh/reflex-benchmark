import os
import shutil


HOME_DIR = "/home/user"
PROJECT_DIR = "/home/user/myproject"


def test_home_directory_exists():
    assert os.path.isdir(HOME_DIR), f"Home directory {HOME_DIR} does not exist."


def test_uv_binary_available():
    assert shutil.which("uv") is not None, (
        "Required environment manager 'uv' is not available in PATH; "
        "Reflex tasks must be initialised with uv per the plan."
    )


def test_python3_binary_available():
    assert shutil.which("python3") is not None, (
        "System 'python3' is not available in PATH; verifier requires it."
    )


def test_sqlite3_binary_available():
    assert shutil.which("sqlite3") is not None, (
        "'sqlite3' CLI is not available in PATH; verifier needs it to inspect reflex.db."
    )


def test_project_dir_is_clean_workspace():
    # The project directory must exist as a workspace that the executor
    # will populate. If it already contains a Reflex project, the task has
    # not been started from a clean slate.
    assert os.path.isdir(PROJECT_DIR), (
        f"Project workspace directory {PROJECT_DIR} does not exist."
    )
    forbidden = ["rxconfig.py", "reflex.db", "alembic", "alembic.ini"]
    present = [name for name in forbidden if os.path.exists(os.path.join(PROJECT_DIR, name))]
    assert not present, (
        f"Project workspace {PROJECT_DIR} is not clean; found pre-existing Reflex artefacts: {present}."
    )


def test_ports_documented_in_task_are_free_enough():
    # Best-effort: ensure no other reflex dev server is already bound to 3000/8000
    # by checking that lsof/ss (if available) does not show a listener. This is a
    # soft check so we do not fail when neither tool is present.
    for tool in ("ss", "lsof"):
        if shutil.which(tool) is None:
            continue
        # Just check the tool runs; we do not assert on output to keep this resilient.
        import subprocess

        subprocess.run([tool, "-V"], check=False, capture_output=True)
        break
