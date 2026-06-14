import os
import socket
import sqlite3
import subprocess
import time

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/wizard_app"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")
FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"
SUBMIT_URL = f"{BACKEND_URL}/api/wizard/submit"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _wait_for_url(url: str, timeout_seconds: int = 180) -> None:
    deadline = time.time() + timeout_seconds
    last_err = None
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code < 500:
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {url}: {last_err!r}")


@pytest.fixture(scope="session")
def start_reflex_app(xprocess):
    """Start the Reflex application in the background and wait for both ports."""

    class Starter(ProcessStarter):
        name = "wizard_reflex_app"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            return _port_open("127.0.0.1", 3000) and _port_open("127.0.0.1", 8000)

    xprocess.ensure(Starter.name, Starter)

    # First page request triggers Reflex to compile any dynamic pages.
    _wait_for_url(f"{FRONTEND_URL}/wizard/profile", timeout_seconds=240)

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()


# -------------------- Routes + step indicator UI --------------------


@pytest.mark.parametrize(
    ("path", "expected_text"),
    [
        ("/wizard/profile", "Step 1 of 4"),
        ("/wizard/address", "Step 2 of 4"),
        ("/wizard/preferences", "Step 3 of 4"),
        ("/wizard/review", "Step 4 of 4"),
    ],
)
def test_step_routes_render_step_indicator(start_reflex_app, path, expected_text):
    url = f"{FRONTEND_URL}{path}"
    resp = requests.get(url, timeout=30)
    assert resp.status_code == 200, (
        f"Expected HTTP 200 from {url}, got {resp.status_code}. Body: {resp.text[:500]!r}"
    )
    assert expected_text in resp.text, (
        f"Expected step indicator '{expected_text}' to be present in the response body "
        f"for {url}, but it was not found. First 500 bytes: {resp.text[:500]!r}"
    )


# -------------------- LocalStorage configuration --------------------


def test_localstorage_key_declared_in_source(start_reflex_app):
    """The state must declare a rx.LocalStorage var keyed as 'wizard_draft'."""
    result = subprocess.run(
        [
            "grep",
            "-R",
            "--include=*.py",
            "-nE",
            r"(rx\.LocalStorage\([^)]*name\s*=\s*[\"']wizard_draft[\"']"
            r"|wizard_draft\s*:\s*str\s*=\s*rx\.LocalStorage)",
            PROJECT_DIR,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and result.stdout.strip(), (
        "Could not find a Python declaration of a rx.LocalStorage var whose "
        "effective key name is 'wizard_draft'. Searched under "
        f"{PROJECT_DIR}. grep stdout: {result.stdout!r}. grep stderr: {result.stderr!r}."
    )


def test_localstorage_key_present_in_compiled_bundle(start_reflex_app):
    """The compiled frontend must reference the 'wizard_draft' storage key."""
    web_dir = os.path.join(PROJECT_DIR, ".web")
    assert os.path.isdir(web_dir), (
        f"Expected compiled frontend directory at {web_dir} after the app started."
    )
    result = subprocess.run(
        ["grep", "-R", "-l", "wizard_draft", web_dir],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and result.stdout.strip(), (
        "Expected the literal 'wizard_draft' to appear in the compiled frontend "
        f"bundle under {web_dir}, but no matches were found."
    )


# -------------------- Validation through the HTTP API --------------------


def test_invalid_email_rejected(start_reflex_app):
    payload = {
        "full_name": "Ada Lovelace",
        "email": "not-an-email",
        "street": "1 Analytical Engine Way",
        "city": "London",
        "postal_code": "12345",
        "newsletter": True,
        "theme": "light",
        "language": "en",
    }
    resp = requests.post(SUBMIT_URL, json=payload, timeout=30)
    assert resp.status_code == 400, (
        f"Expected HTTP 400 for invalid email, got {resp.status_code}. "
        f"Body: {resp.text[:500]!r}"
    )
    body = resp.json()
    assert isinstance(body, dict) and isinstance(body.get("errors"), dict), (
        f"Expected JSON body shaped as {{'errors': {{...}}}}, got {body!r}."
    )
    assert "email" in body["errors"], (
        f"Expected 'email' key in errors object, got: {body['errors']!r}."
    )


def test_invalid_postal_code_rejected(start_reflex_app):
    payload = {
        "full_name": "Grace Hopper",
        "email": "grace@example.com",
        "street": "123 Main St",
        "city": "Arlington",
        "postal_code": "ABCDE",
        "newsletter": False,
        "theme": "dark",
        "language": "en",
    }
    resp = requests.post(SUBMIT_URL, json=payload, timeout=30)
    assert resp.status_code == 400, (
        f"Expected HTTP 400 for invalid postal code, got {resp.status_code}. "
        f"Body: {resp.text[:500]!r}"
    )
    body = resp.json()
    assert isinstance(body, dict) and isinstance(body.get("errors"), dict), (
        f"Expected JSON body shaped as {{'errors': {{...}}}}, got {body!r}."
    )
    assert "postal_code" in body["errors"], (
        f"Expected 'postal_code' key in errors object, got: {body['errors']!r}."
    )


def test_invalid_theme_and_language_rejected(start_reflex_app):
    payload = {
        "full_name": "Linus Torvalds",
        "email": "linus@example.com",
        "street": "1 Kernel Way",
        "city": "Helsinki",
        "postal_code": "00100",
        "newsletter": True,
        "theme": "neon",
        "language": "EN",
    }
    resp = requests.post(SUBMIT_URL, json=payload, timeout=30)
    assert resp.status_code == 400, (
        f"Expected HTTP 400 for invalid theme/language, got {resp.status_code}. "
        f"Body: {resp.text[:500]!r}"
    )
    body = resp.json()
    assert isinstance(body, dict) and isinstance(body.get("errors"), dict), (
        f"Expected JSON body shaped as {{'errors': {{...}}}}, got {body!r}."
    )
    errors = body["errors"]
    assert "theme" in errors, (
        f"Expected 'theme' key in errors object for theme='neon', got: {errors!r}."
    )
    assert "language" in errors, (
        f"Expected 'language' key in errors object for language='EN', got: {errors!r}."
    )


# -------------------- Successful submission + SQLite row --------------------


def test_successful_submission_writes_sqlite_row(start_reflex_app):
    payload = {
        "full_name": "Margaret Hamilton",
        "email": "margaret@apollo.example.com",
        "street": "500 Tech Square",
        "city": "Cambridge",
        "postal_code": "02139",
        "newsletter": True,
        "theme": "dark",
        "language": "en",
    }
    resp = requests.post(SUBMIT_URL, json=payload, timeout=30)
    assert resp.status_code == 200, (
        f"Expected HTTP 200 for a valid submission, got {resp.status_code}. "
        f"Body: {resp.text[:500]!r}"
    )
    body = resp.json()
    assert isinstance(body, dict) and isinstance(body.get("id"), int), (
        f"Expected JSON body shaped as {{'id': <int>}}, got {body!r}."
    )
    row_id = body["id"]

    assert os.path.isfile(DB_PATH), (
        f"Expected SQLite database file at {DB_PATH} after a successful submission."
    )

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT full_name, email, street, city, postal_code, "
            "newsletter, theme, language, created_at "
            "FROM submission WHERE id = ?",
            (row_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    assert row is not None, (
        f"Expected a row with id={row_id} in the 'submission' table at {DB_PATH}, "
        "but none was found."
    )

    (
        full_name,
        email,
        street,
        city,
        postal_code,
        newsletter,
        theme,
        language,
        created_at,
    ) = row

    assert full_name == "Margaret Hamilton", (
        f"Expected full_name='Margaret Hamilton', got {full_name!r}."
    )
    assert email == "margaret@apollo.example.com", (
        f"Expected email='margaret@apollo.example.com', got {email!r}."
    )
    assert street == "500 Tech Square", (
        f"Expected street='500 Tech Square', got {street!r}."
    )
    assert city == "Cambridge", f"Expected city='Cambridge', got {city!r}."
    assert postal_code == "02139", (
        f"Expected postal_code='02139', got {postal_code!r}."
    )
    assert bool(newsletter) is True, (
        f"Expected newsletter to be truthy (True/1), got {newsletter!r}."
    )
    assert theme == "dark", f"Expected theme='dark', got {theme!r}."
    assert language == "en", f"Expected language='en', got {language!r}."
    assert created_at is not None and str(created_at).strip() != "", (
        f"Expected a non-empty created_at value on the submission row, got {created_at!r}."
    )
