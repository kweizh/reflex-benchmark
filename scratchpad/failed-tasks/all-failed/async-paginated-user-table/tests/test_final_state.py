import ast
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/myproject"
SQLITE_DB = os.path.join(PROJECT_DIR, "reflex.db")
FRONTEND_PORT = 3000
BACKEND_PORT = 8000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_python_files(root: str):
    skip_dirs = {".web", ".states", "__pycache__", ".venv", "venv", "alembic", "assets"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fname in filenames:
            if fname.endswith(".py"):
                yield os.path.join(dirpath, fname)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _find_user_model_file():
    """Return (path, ast.ClassDef) of the `class User(rx.Model, table=True)` declaration."""
    for path in _iter_python_files(PROJECT_DIR):
        try:
            tree = ast.parse(_read_text(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name != "User":
                continue
            # check bases for rx.Model
            has_rx_model_base = False
            for base in node.bases:
                if isinstance(base, ast.Attribute) and base.attr == "Model":
                    if isinstance(base.value, ast.Name) and base.value.id == "rx":
                        has_rx_model_base = True
            # check keywords for table=True
            has_table_true = False
            for kw in node.keywords:
                if kw.arg == "table" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    has_table_true = True
            if has_rx_model_base and has_table_true:
                return path, node
    return None, None


def _find_background_event_functions():
    """Yield (path, ast.AsyncFunctionDef, source_text) for any function decorated with @rx.event(background=True)."""
    matches = []
    for path in _iter_python_files(PROJECT_DIR):
        source = _read_text(path)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                func = dec.func
                # rx.event(background=True)
                if isinstance(func, ast.Attribute) and func.attr == "event":
                    if isinstance(func.value, ast.Name) and func.value.id == "rx":
                        for kw in dec.keywords:
                            if (
                                kw.arg == "background"
                                and isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            ):
                                fn_source = ast.get_source_segment(source, node) or ""
                                matches.append((path, node, fn_source))
    return matches


def _wait_for_port(host: str, port: int, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            try:
                if s.connect_ex((host, port)) == 0:
                    return True
            except OSError:
                pass
        time.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Static AST verification
# ---------------------------------------------------------------------------


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected the Reflex project directory at {PROJECT_DIR}."
    )


def test_user_model_declared_as_rx_model_table():
    path, node = _find_user_model_file()
    assert node is not None, (
        "Could not find `class User(rx.Model, table=True)` anywhere under the project."
    )
    # Inspect annotated assignments inside class body for username: str and email: str
    field_types: dict[str, str] = {}
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            ann_src = ast.unparse(stmt.annotation) if hasattr(ast, "unparse") else ""
            field_types[stmt.target.id] = ann_src
    assert "username" in field_types and "str" in field_types["username"], (
        f"User model is missing required `username: str` field. Found: {field_types}"
    )
    assert "email" in field_types and "str" in field_types["email"], (
        f"User model is missing required `email: str` field. Found: {field_types}"
    )


def test_background_event_uses_async_session_and_state_lock():
    matches = _find_background_event_functions()
    assert matches, (
        "No async function decorated with @rx.event(background=True) was found in the project."
    )
    ok = False
    for _path, _node, src in matches:
        if "async with rx.asession()" in src and "async with self:" in src:
            ok = True
            break
    assert ok, (
        "Expected a @rx.event(background=True) handler that uses both "
        "`async with rx.asession()` and `async with self:` blocks."
    )


def test_state_declares_pagination_vars():
    """Search for `page`, `page_size`, `users` declared on an rx.State subclass."""
    found_page = False
    found_page_size = False
    found_users = False
    for path in _iter_python_files(PROJECT_DIR):
        source = _read_text(path)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            is_state = False
            for base in cls.bases:
                if isinstance(base, ast.Attribute) and base.attr == "State":
                    if isinstance(base.value, ast.Name) and base.value.id == "rx":
                        is_state = True
                # Allow inheritance from a custom State subclass too
                if isinstance(base, ast.Name) and base.id.endswith("State"):
                    is_state = True
            if not is_state:
                continue
            for stmt in cls.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    name = stmt.target.id
                    if name == "page":
                        found_page = True
                    elif name == "page_size":
                        found_page_size = True
                    elif name == "users":
                        found_users = True
    assert found_page, "Expected an `rx.State` subclass to declare a `page` annotated var."
    assert found_page_size, "Expected an `rx.State` subclass to declare a `page_size` annotated var."
    assert found_users, "Expected an `rx.State` subclass to declare a `users` annotated var."


# ---------------------------------------------------------------------------
# Database migrations & schema verification
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def migrated_database():
    # Clean any previous run
    if os.path.isfile(SQLITE_DB):
        os.remove(SQLITE_DB)

    env = os.environ.copy()

    init_proc = subprocess.run(
        ["uv", "run", "reflex", "db", "init"],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    # `db init` is idempotent and may exit non-zero if already initialised; ignore that case
    assert "error" not in (init_proc.stderr or "").lower() or "already" in (init_proc.stderr or "").lower() or init_proc.returncode == 0, (
        f"`uv run reflex db init` failed unexpectedly: stdout={init_proc.stdout}, stderr={init_proc.stderr}"
    )

    mig_proc = subprocess.run(
        ["uv", "run", "reflex", "db", "makemigrations", "--message", "initial schema"],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert mig_proc.returncode == 0, (
        f"`uv run reflex db makemigrations` failed: stdout={mig_proc.stdout}, stderr={mig_proc.stderr}"
    )

    migrate_proc = subprocess.run(
        ["uv", "run", "reflex", "db", "migrate"],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert migrate_proc.returncode == 0, (
        f"`uv run reflex db migrate` failed: stdout={migrate_proc.stdout}, stderr={migrate_proc.stderr}"
    )
    yield SQLITE_DB


def test_sqlite_db_file_created(migrated_database):
    assert os.path.isfile(migrated_database), (
        f"Expected SQLite database at {migrated_database} after running Reflex migrations."
    )


def test_user_table_schema(migrated_database):
    result = subprocess.run(
        ["sqlite3", migrated_database, ".schema user"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Failed to inspect schema with sqlite3: {result.stderr}"
    )
    schema = result.stdout
    assert "CREATE TABLE" in schema.upper() and "user" in schema.lower(), (
        f"Expected a CREATE TABLE statement for `user` in the schema, got: {schema}"
    )
    lowered = schema.lower()
    for required_col in ("id", "username", "email"):
        assert required_col in lowered, (
            f"Expected column `{required_col}` in the `user` table schema. Got: {schema}"
        )


# ---------------------------------------------------------------------------
# Frontend export verification
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def exported_frontend(migrated_database):
    env = os.environ.copy()
    proc = subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, (
        f"`uv run reflex export --frontend-only --no-zip` failed: "
        f"stdout={proc.stdout}, stderr={proc.stderr}"
    )

    # Reflex emits the frontend assets under `.web` (legacy) or `frontend.zip` extracted dir.
    candidate_roots = [
        Path(PROJECT_DIR) / ".web",
        Path(PROJECT_DIR) / "frontend",
    ]
    roots = [p for p in candidate_roots if p.exists()]
    assert roots, (
        "Could not find any exported frontend directory (.web/ or frontend/) after `reflex export`."
    )
    yield roots


def test_exported_frontend_contains_bindings_and_labels(exported_frontend):
    needles = ["Prev", "Next", "users", "page_size", "page"]
    found: dict[str, bool] = {n: False for n in needles}
    for root in exported_frontend:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip node_modules to keep the scan fast and avoid false positives from third-party JS.
            dirnames[:] = [d for d in dirnames if d not in {"node_modules", ".next/cache"}]
            for fname in filenames:
                if not fname.endswith((".js", ".jsx", ".ts", ".tsx", ".html", ".json", ".mjs", ".cjs")):
                    continue
                fp = os.path.join(dirpath, fname)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except OSError:
                    continue
                for n in needles:
                    if not found[n] and n in content:
                        found[n] = True
                if all(found.values()):
                    break
            if all(found.values()):
                break
        if all(found.values()):
            break
    missing = [k for k, v in found.items() if not v]
    assert not missing, (
        f"Exported frontend bundle is missing required tokens: {missing}. "
        "Expected to find Prev/Next button labels and bindings for users/page/page_size."
    )


# ---------------------------------------------------------------------------
# Live dev server verification
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def reflex_dev_server(xprocess, migrated_database):
    class Starter(ProcessStarter):
        name = "reflex_dev"
        args = ["uv", "run", "reflex", "run", "--env", "dev", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            # Consider ready when both backend (8000) and frontend (3000) accept connections.
            for port in (BACKEND_PORT, FRONTEND_PORT):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    if s.connect_ex(("127.0.0.1", port)) != 0:
                        return False
            return True

    xprocess.ensure(Starter.name, Starter)
    # Give the frontend an extra moment to finish its first compile after the port opens.
    assert _wait_for_port("127.0.0.1", FRONTEND_PORT, timeout=300), (
        "Reflex frontend never started listening on port 3000."
    )
    time.sleep(5)
    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()


def test_index_page_renders_table_and_buttons(reflex_dev_server):
    last_err: Exception | None = None
    body = ""
    for _ in range(30):
        try:
            resp = requests.get(f"http://127.0.0.1:{FRONTEND_PORT}/", timeout=10)
            if resp.status_code < 500:
                body = resp.text
                break
        except requests.RequestException as e:
            last_err = e
        time.sleep(2)
    else:
        raise AssertionError(
            f"Failed to fetch / from the Reflex dev server: {last_err}"
        )

    assert "Prev" in body, "Expected the rendered index page to contain a 'Prev' button label."
    assert "Next" in body, "Expected the rendered index page to contain a 'Next' button label."
    assert "<table" in body.lower(), "Expected the rendered index page to contain a <table> element."
