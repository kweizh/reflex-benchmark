import shutil


def test_uv_available():
    assert shutil.which("uv") is not None, (
        "The 'uv' package manager is required to manage the Reflex project "
        "environment but was not found in PATH."
    )


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 is required but was not found in PATH."
    )
