import json
import os
import re
import socket
import subprocess
import time

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/myproject"
BACKEND_BASE = "http://127.0.0.1:8000"
FRONTEND_BASE = "http://127.0.0.1:3000"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000

REQUIRED_IDS = [
    "room-list",
    "add-room-input",
    "add-room-button",
    "current-room-title",
    "message-list",
    "message-input",
    "send-button",
]


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _kill_ports():
    # Best-effort kill of anything previously bound to the Reflex ports.
    for port in (FRONTEND_PORT, BACKEND_PORT):
        subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            capture_output=True,
            text=True,
        )


@pytest.fixture(scope="session")
def reflex_app(xprocess):
    _kill_ports()

    log_path = os.path.join(PROJECT_DIR, "verifier.log")
    if os.path.isfile(log_path):
        try:
            os.remove(log_path)
        except OSError:
            pass

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run", "--env", "prod", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open(BACKEND_PORT):
                return False
            if not _port_open(FRONTEND_PORT):
                return False
            try:
                r = requests.get(f"{BACKEND_BASE}/api/rooms", timeout=5)
                if r.status_code != 200:
                    return False
            except requests.RequestException:
                return False
            try:
                r = requests.get(FRONTEND_BASE, timeout=10)
                if r.status_code != 200:
                    return False
            except requests.RequestException:
                return False
            return True

    xprocess.ensure(Starter.name, Starter)

    # Give Reflex a small extra grace period after startup_check passes.
    time.sleep(2)

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    _kill_ports()


def test_pyproject_declares_reflex():
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")
    assert os.path.isfile(pyproject), (
        f"Expected uv-managed project file {pyproject} to exist."
    )
    with open(pyproject, "r", encoding="utf-8") as f:
        content = f.read()
    assert re.search(r"reflex", content, re.IGNORECASE), (
        "pyproject.toml does not declare a `reflex` dependency."
    )


def test_database_schema_contains_message_table(reflex_app):
    db_path = os.path.join(PROJECT_DIR, "reflex.db")
    assert os.path.isfile(db_path), f"SQLite database file {db_path} does not exist."

    result = subprocess.run(
        ["sqlite3", db_path, ".schema message"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`sqlite3 .schema message` failed: stderr={result.stderr!r}"
    )
    schema = result.stdout.lower()
    assert "create table" in schema and "message" in schema, (
        f"Expected a `message` table in {db_path}, got schema: {result.stdout!r}"
    )
    for column in ("id", "room", "sender", "content", "created_at"):
        assert column in schema, (
            f"Expected column `{column}` in the `message` table schema, got: {result.stdout!r}"
        )


def test_seed_rooms_present(reflex_app):
    r = requests.get(f"{BACKEND_BASE}/api/rooms", timeout=10)
    assert r.status_code == 200, (
        f"GET /api/rooms returned {r.status_code}, body={r.text!r}"
    )
    payload = r.json()
    assert isinstance(payload, dict) and "rooms" in payload, (
        f"GET /api/rooms must return an object with key 'rooms', got: {payload!r}"
    )
    rooms = payload["rooms"]
    assert isinstance(rooms, list), (
        f"`rooms` must be a list, got type {type(rooms).__name__}"
    )
    for required in ("general", "random"):
        assert required in rooms, (
            f"Expected seed room {required!r} to be in /api/rooms response, got: {rooms!r}"
        )


def test_dynamic_room_creation(reflex_app):
    create = requests.post(
        f"{BACKEND_BASE}/api/rooms",
        json={"name": "engineering"},
        timeout=10,
    )
    assert create.status_code == 201, (
        f"POST /api/rooms with body {{'name': 'engineering'}} returned "
        f"{create.status_code}, body={create.text!r}"
    )
    body = create.json()
    assert body.get("name") == "engineering", (
        f"Expected response body {{'name': 'engineering'}}, got {body!r}"
    )

    listing = requests.get(f"{BACKEND_BASE}/api/rooms", timeout=10).json()
    assert "engineering" in listing.get("rooms", []), (
        f"Newly created room 'engineering' did not appear in /api/rooms listing: {listing!r}"
    )


def test_duplicate_room_rejected(reflex_app):
    r = requests.post(
        f"{BACKEND_BASE}/api/rooms",
        json={"name": "general"},
        timeout=10,
    )
    assert r.status_code == 409, (
        f"POST /api/rooms with duplicate name should return 409, got {r.status_code}, "
        f"body={r.text!r}"
    )


def test_empty_room_rejected(reflex_app):
    r = requests.post(
        f"{BACKEND_BASE}/api/rooms",
        json={"name": ""},
        timeout=10,
    )
    assert r.status_code == 400, (
        f"POST /api/rooms with empty name should return 400, got {r.status_code}, "
        f"body={r.text!r}"
    )


def test_send_message_streams_assistant_reply(reflex_app):
    # Ensure the engineering room exists before sending a message.
    requests.post(
        f"{BACKEND_BASE}/api/rooms",
        json={"name": "engineering"},
        timeout=10,
    )

    r = requests.post(
        f"{BACKEND_BASE}/api/messages",
        json={"room": "engineering", "content": "Hello there"},
        timeout=60,
    )
    assert r.status_code == 200, (
        f"POST /api/messages returned {r.status_code}, body={r.text!r}"
    )
    payload = r.json()

    user_msg = payload.get("user_message")
    chunks = payload.get("assistant_chunks")
    assistant_msg = payload.get("assistant_message")

    assert isinstance(user_msg, dict), (
        f"`user_message` must be an object, got: {user_msg!r}"
    )
    assert user_msg.get("room") == "engineering", (
        f"user_message.room must be 'engineering', got {user_msg!r}"
    )
    assert user_msg.get("sender") == "user", (
        f"user_message.sender must be 'user', got {user_msg!r}"
    )
    assert user_msg.get("content") == "Hello there", (
        f"user_message.content must be 'Hello there', got {user_msg!r}"
    )
    assert isinstance(user_msg.get("id"), int), (
        f"user_message.id must be int, got {user_msg!r}"
    )
    assert isinstance(user_msg.get("created_at"), str), (
        f"user_message.created_at must be str, got {user_msg!r}"
    )

    assert isinstance(chunks, list), (
        f"`assistant_chunks` must be a list, got: {chunks!r}"
    )
    assert len(chunks) >= 5, (
        f"`assistant_chunks` must contain at least 5 incremental updates, got {len(chunks)}: {chunks!r}"
    )
    for chunk in chunks:
        assert isinstance(chunk, str) and len(chunk) > 0, (
            f"Every assistant chunk must be a non-empty string, got: {chunks!r}"
        )

    assert isinstance(assistant_msg, dict), (
        f"`assistant_message` must be an object, got: {assistant_msg!r}"
    )
    assert assistant_msg.get("room") == "engineering", (
        f"assistant_message.room must be 'engineering', got {assistant_msg!r}"
    )
    assert assistant_msg.get("sender") == "assistant", (
        f"assistant_message.sender must be 'assistant', got {assistant_msg!r}"
    )
    assert isinstance(assistant_msg.get("content"), str) and assistant_msg["content"], (
        f"assistant_message.content must be a non-empty string, got {assistant_msg!r}"
    )
    assert "".join(chunks) == assistant_msg["content"], (
        f"Concatenated `assistant_chunks` must equal `assistant_message.content`. "
        f"chunks={chunks!r}, content={assistant_msg.get('content')!r}"
    )


def test_messages_persisted(reflex_app):
    r = requests.get(
        f"{BACKEND_BASE}/api/messages",
        params={"room": "engineering"},
        timeout=10,
    )
    assert r.status_code == 200, (
        f"GET /api/messages?room=engineering returned {r.status_code}, body={r.text!r}"
    )
    body = r.json()
    assert body.get("room") == "engineering", (
        f"Response must include 'room': 'engineering', got {body!r}"
    )
    messages = body.get("messages")
    assert isinstance(messages, list) and len(messages) >= 2, (
        f"Expected at least 2 persisted messages in 'engineering', got {messages!r}"
    )

    senders = [m.get("sender") for m in messages]
    assert "user" in senders, (
        f"Expected a persisted user message in 'engineering', senders={senders!r}"
    )
    assert "assistant" in senders, (
        f"Expected a persisted assistant message in 'engineering', senders={senders!r}"
    )

    user_msgs = [m for m in messages if m.get("sender") == "user"]
    assert any(m.get("content") == "Hello there" for m in user_msgs), (
        f"Expected a persisted user message with content 'Hello there', got: {user_msgs!r}"
    )

    # Ensure ordering is oldest-first by created_at.
    timestamps = [m.get("created_at") for m in messages]
    assert timestamps == sorted(timestamps), (
        f"Messages must be returned oldest-first by created_at, got order: {timestamps!r}"
    )


def test_unknown_room_send_rejected(reflex_app):
    r = requests.post(
        f"{BACKEND_BASE}/api/messages",
        json={"room": "does-not-exist", "content": "hi"},
        timeout=10,
    )
    assert r.status_code == 404, (
        f"POST /api/messages targeting an unknown room must return 404, "
        f"got {r.status_code}, body={r.text!r}"
    )


def test_frontend_html_contains_required_ids(reflex_app):
    r = requests.get(FRONTEND_BASE, timeout=30, allow_redirects=True)
    assert r.status_code == 200, (
        f"GET {FRONTEND_BASE} returned {r.status_code}, body[:200]={r.text[:200]!r}"
    )
    html = r.text

    # Reflex compiles to Next.js; the initial HTML payload should contain hydration
    # data referencing the explicit `id` props we set on Reflex components.
    for required_id in REQUIRED_IDS:
        needle = f'id="{required_id}"'
        assert needle in html, (
            f"Expected the frontend HTML at {FRONTEND_BASE} to contain `{needle}`, "
            "but it was not found."
        )

    assert 'id="empty-room-placeholder"' in html, (
        "Expected the frontend HTML to contain `id=\"empty-room-placeholder\"` "
        "for the conditional empty-room state, but it was not found."
    )
