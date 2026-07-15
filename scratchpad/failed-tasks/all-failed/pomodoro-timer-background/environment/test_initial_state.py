import shutil


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager is required to build and run the Reflex app "
        "but was not found in PATH."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 is required but was not found in PATH."
    )


def test_sqlite3_available():
    assert shutil.which("sqlite3") is not None, (
        "The 'sqlite3' CLI is required to verify the local database but was not "
        "found in PATH."
    )
