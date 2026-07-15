import hashlib
import importlib.util
import os
import socket
import sqlite3
import sys
import tempfile
import types

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/registration_wizard"
VALIDATORS_PATH = os.path.join(PROJECT_DIR, "validators.py")
DB_PATH = os.path.join(PROJECT_DIR, "db.py")
DB_FILE = os.path.join(PROJECT_DIR, "registration.db")

FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly to avoid IPv6 loopback (::1) resolution issues.
HOST = "127.0.0.1"
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"


def _load_module(path: str, name: str) -> types.ModuleType:
    assert os.path.isfile(path), f"Required module {path} does not exist."
    # Make the project root importable so intra-project imports resolve.
    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"Could not load module spec for {path}."
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def validators_module() -> types.ModuleType:
    return _load_module(VALIDATORS_PATH, "wizard_validators")


@pytest.fixture(scope="session")
def db_module() -> types.ModuleType:
    return _load_module(DB_PATH, "wizard_db")


# ---------------------------------------------------------------------------
# Section A: validators.py server-side validation
# ---------------------------------------------------------------------------


def test_step1_valid_email(validators_module):
    result = validators_module.validate_step(1, {"email": "alice@example.com"})
    assert result == {}, f"Valid email should produce no errors, got: {result}"


def test_step1_blank_email(validators_module):
    result = validators_module.validate_step(1, {"email": "   "})
    assert result.get("email") == "Email is required", \
        f"Blank email should report 'Email is required', got: {result}"


def test_step1_malformed_email(validators_module):
    result = validators_module.validate_step(1, {"email": "not-an-email"})
    assert result.get("email") == "Invalid email address", \
        f"Malformed email should report 'Invalid email address', got: {result}"


def test_step2_valid_password(validators_module):
    result = validators_module.validate_step(
        2, {"password": "Abcd1234", "confirm_password": "Abcd1234"}
    )
    assert result == {}, f"Valid password/confirm should produce no errors, got: {result}"


def test_step2_password_too_short(validators_module):
    result = validators_module.validate_step(
        2, {"password": "Ab1", "confirm_password": "Ab1"}
    )
    assert result.get("password") == "Password must be at least 8 characters", \
        f"Short password should report length error, got: {result}"


def test_step2_password_no_uppercase(validators_module):
    result = validators_module.validate_step(
        2, {"password": "abcd1234", "confirm_password": "abcd1234"}
    )
    assert result.get("password") == "Password must contain an uppercase letter", \
        f"Password without uppercase should report uppercase error, got: {result}"


def test_step2_password_no_lowercase(validators_module):
    result = validators_module.validate_step(
        2, {"password": "ABCD1234", "confirm_password": "ABCD1234"}
    )
    assert result.get("password") == "Password must contain a lowercase letter", \
        f"Password without lowercase should report lowercase error, got: {result}"


def test_step2_password_no_digit(validators_module):
    result = validators_module.validate_step(
        2, {"password": "Abcdefgh", "confirm_password": "Abcdefgh"}
    )
    assert result.get("password") == "Password must contain a digit", \
        f"Password without digit should report digit error, got: {result}"


def test_step2_password_mismatch(validators_module):
    result = validators_module.validate_step(
        2, {"password": "Abcd1234", "confirm_password": "Zzzz9999"}
    )
    assert result.get("confirm_password") == "Passwords do not match", \
        f"Mismatched confirm should report mismatch error, got: {result}"


def test_step3_valid(validators_module):
    result = validators_module.validate_step(
        3, {"full_name": "Alice Smith", "accept_terms": True}
    )
    assert result == {}, f"Valid step 3 should produce no errors, got: {result}"


def test_step3_blank_full_name(validators_module):
    result = validators_module.validate_step(
        3, {"full_name": "  ", "accept_terms": True}
    )
    assert result.get("full_name") == "Full name is required", \
        f"Blank full name should report required error, got: {result}"


def test_step3_terms_not_accepted(validators_module):
    result = validators_module.validate_step(
        3, {"full_name": "Alice Smith", "accept_terms": False}
    )
    assert result.get("accept_terms") == "You must accept the terms", \
        f"Unaccepted terms should report terms error, got: {result}"


# ---------------------------------------------------------------------------
# Section B: db.py SQLite persistence
# ---------------------------------------------------------------------------


def test_db_path_constant(db_module):
    assert isinstance(db_module.DB_PATH, str), "DB_PATH must be a string."
    assert db_module.DB_PATH.endswith("registration.db"), \
        f"DB_PATH should point to registration.db, got: {db_module.DB_PATH}"


def test_init_db_creates_schema(db_module):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = os.path.join(tmp, "registration.db")
        db_module.init_db(tmp_db)
        conn = sqlite3.connect(tmp_db)
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(registrations)").fetchall()}
        finally:
            conn.close()
        expected = {"id", "email", "full_name", "password_hash", "created_at"}
        assert expected.issubset(cols), \
            f"registrations table must contain columns {expected}, got: {cols}"


def test_insert_registration_persists_row(db_module):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = os.path.join(tmp, "registration.db")
        db_module.init_db(tmp_db)
        new_id = db_module.insert_registration("bob@example.com", "Bob Jones", "Secret123", tmp_db)
        assert isinstance(new_id, int) and new_id > 0, \
            f"insert_registration should return a positive int id, got: {new_id!r}"

        conn = sqlite3.connect(tmp_db)
        try:
            row = conn.execute(
                "SELECT email, full_name, password_hash, created_at FROM registrations WHERE id = ?",
                (new_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, "Inserted registration row was not found."
        email, full_name, password_hash, created_at = row
        assert email == "bob@example.com", f"Unexpected email persisted: {email}"
        assert full_name == "Bob Jones", f"Unexpected full_name persisted: {full_name}"
        expected_hash = hashlib.sha256(b"Secret123").hexdigest()
        assert password_hash == expected_hash, \
            f"password_hash should be the SHA-256 hex digest of the password, got: {password_hash}"
        assert isinstance(created_at, str) and created_at.strip() != "", \
            f"created_at should be a non-empty string, got: {created_at!r}"


# ---------------------------------------------------------------------------
# Section C: Reflex wiring (static inspection of the app sources)
# ---------------------------------------------------------------------------


def _app_source_text() -> str:
    """Concatenate all project .py sources except the two helper modules."""
    chunks = []
    for root, _dirs, files in os.walk(PROJECT_DIR):
        # skip virtualenv / build / cache directories
        if any(part in root for part in (".venv", "node_modules", ".web", "__pycache__", ".states")):
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            if fname in ("validators.py", "db.py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    chunks.append(f.read())
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(chunks)


def test_app_defines_reflex_state():
    source = _app_source_text()
    assert "rx.State" in source, \
        "The app should define a Reflex state that subclasses rx.State."


def test_app_uses_validate_step():
    source = _app_source_text()
    assert "validate_step" in source, \
        "The app state should call validate_step to guard step advancement/submission."


def test_app_uses_persistence():
    source = _app_source_text()
    assert "insert_registration" in source, \
        "The app should call insert_registration on successful final submit."
    assert "init_db" in source, \
        "The app should call init_db so the registrations table exists at startup."


def test_app_uses_cond():
    source = _app_source_text()
    assert "rx.cond" in source, \
        "The app should use rx.cond for conditional rendering of steps/errors."


def test_app_defines_computed_vars():
    source = _app_source_text()
    assert source.count("@rx.var") >= 2, \
        "The app should define at least two @rx.var computed vars (step label and progress)."


# ---------------------------------------------------------------------------
# Section D: Runtime smoke test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def reflex_server(xprocess):
    class Starter(ProcessStarter):
        name = "reflex_server"
        args = ["uv", "run", "reflex", "run"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the frontend and may fetch frontend deps; allow ample time.
        timeout = 420
        terminate_on_interrupt = True

        def startup_check(self):
            # Readiness == backend is up and answers the health route with "pong".
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, BACKEND_PORT)) != 0:
                    return False
            try:
                resp = requests.get(f"{BACKEND_URL}/ping", timeout=20)
            except requests.RequestException:
                return False
            return resp.status_code == 200 and "pong" in resp.text.lower()

    info = xprocess.getinfo(Starter.name)
    printed = 0

    def capture_logs(tag):
        nonlocal printed
        try:
            with open(info.logpath, "r") as f:
                lines = f.readlines()
        except OSError:
            return
        new = lines[printed:]
        printed = len(lines)
        print(f"===== [{tag}] reflex_server log =====")
        print("".join(new))
        print(f"===== [{tag}] end reflex_server log =====")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield
    capture_logs("TEARDOWN")
    info.terminate()


def test_backend_ping(reflex_server):
    resp = requests.get(f"{BACKEND_URL}/ping", timeout=30)
    assert resp.status_code == 200, f"Backend /ping returned status {resp.status_code}"
    assert "pong" in resp.text.lower(), f"Backend /ping should return 'pong', got: {resp.text!r}"


def test_frontend_serves_wizard(reflex_server):
    # The frontend dev server compiles the page on first request; retry a few times.
    last_exc = None
    body = ""
    status = None
    for _ in range(15):
        try:
            resp = requests.get(f"{FRONTEND_URL}/", timeout=30)
            status = resp.status_code
            body = resp.text
            if status == 200 and "registration wizard" in body.lower():
                break
        except requests.RequestException as exc:  # noqa: PERF203
            last_exc = exc
        import time
        time.sleep(5)
    assert last_exc is None or status == 200, \
        f"Failed to load the frontend page at {FRONTEND_URL}: {last_exc}"
    assert status == 200, f"Frontend root returned status {status}"
    assert "registration wizard" in body.lower(), \
        "The frontend page should carry the document title 'Registration Wizard'."


def test_startup_creates_database(reflex_server):
    assert os.path.isfile(DB_FILE), \
        f"Expected the app to create the SQLite database at {DB_FILE} on startup."
    conn = sqlite3.connect(DB_FILE)
    try:
        found = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='registrations'"
        ).fetchone()
    finally:
        conn.close()
    assert found is not None, \
        "The 'registrations' table should exist in the app's SQLite database after startup."
