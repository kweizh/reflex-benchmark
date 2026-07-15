import hashlib
import importlib.util
import os
import re
import socket

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/hashworker"
HASH_CORE_PATH = os.path.join(PROJECT_DIR, "hash_core.py")

# Connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) on some stacks while the dev server only listens on 127.0.0.1, which
# would make readiness/connection checks hang.
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_hash_core():
    assert os.path.isfile(HASH_CORE_PATH), (
        f"Expected the pure-Python logic module at {HASH_CORE_PATH}, but it "
        "does not exist."
    )
    spec = importlib.util.spec_from_file_location("hash_core", HASH_CORE_PATH)
    assert spec is not None and spec.loader is not None, (
        f"Could not create an import spec for {HASH_CORE_PATH}."
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"Failed to import {HASH_CORE_PATH} with system python3 "
            f"(it must not depend on Reflex): {exc}"
        ) from exc
    return module


def _collect_source() -> str:
    """Concatenate the project's own .py sources (excluding envs/build dirs)."""
    skip_dirs = {".venv", ".web", "__pycache__", ".git", "node_modules"}
    chunks = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(root, name)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        chunks.append(f.read())
                except OSError:
                    continue
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# Long-running Reflex dev server fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def start_app(xprocess):
    class Starter(ProcessStarter):
        name = "reflex_hash_worker"
        args = ["uv", "run", "reflex", "run", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # The first `reflex run` compiles the frontend (installs bun/node deps),
        # which can take a while.
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
            try:
                resp = requests.get(BASE_URL, timeout=30)
                return resp.status_code < 500
            except requests.RequestException:
                return False

    info = xprocess.getinfo(Starter.name)
    printed_log_lines = 0

    def capture_logs(tag):
        nonlocal printed_log_lines
        try:
            with open(info.logpath, "r") as f:
                all_lines = f.readlines()
        except OSError:
            all_lines = []
        new_lines = all_lines[printed_log_lines:]
        printed_log_lines = len(all_lines)
        print(f"===== [{tag}] {Starter.name} log begin =====")
        print("".join(new_lines))
        print(f"===== [{tag}] {Starter.name} log end   =====")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


# ---------------------------------------------------------------------------
# Step 1: pure hashing logic module (no server, no Reflex required)
# ---------------------------------------------------------------------------
def test_generate_records_shape_and_determinism():
    core = _load_hash_core()
    assert hasattr(core, "generate_records"), (
        "hash_core must expose a `generate_records(count, seed)` function."
    )
    recs = core.generate_records(5, "zseed")
    assert isinstance(recs, list) and len(recs) == 5, (
        f"generate_records(5, 'zseed') must return a list of length 5, got {recs!r}."
    )
    for rec in recs:
        assert isinstance(rec, dict), f"Each record must be a dict, got {rec!r}."
        assert set(rec.keys()) == {"name", "content"}, (
            f"Each record must have exactly keys 'name' and 'content', got {sorted(rec.keys())}."
        )
        assert isinstance(rec["name"], str) and isinstance(rec["content"], str), (
            f"Record 'name' and 'content' must both be strings, got {rec!r}."
        )

    recs_again = core.generate_records(5, "zseed")
    assert recs_again == recs, (
        "generate_records must be deterministic for the same (count, seed)."
    )

    other = core.generate_records(5, "other")
    assert [r["content"] for r in other] != [r["content"] for r in recs], (
        "generate_records must produce different content for a different seed."
    )


def test_hash_record_matches_sha256():
    core = _load_hash_core()
    assert hasattr(core, "hash_record"), (
        "hash_core must expose a `hash_record(content)` function."
    )
    recs = core.generate_records(5, "zseed")
    for rec in recs:
        content = rec["content"]
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        actual = core.hash_record(content)
        assert actual == expected, (
            f"hash_record({content!r}) returned {actual!r}, expected SHA-256 "
            f"hex digest {expected!r}."
        )


# ---------------------------------------------------------------------------
# Step 2: required Reflex primitives are actually used
# ---------------------------------------------------------------------------
def test_reflex_primitives_present():
    src = _collect_source()
    assert src.strip(), f"No Python source files found under {PROJECT_DIR}."

    assert "background=True" in src, (
        "Expected a background task declared with `@rx.event(background=True)`."
    )
    assert "async with self" in src, (
        "Background task must mutate state inside an `async with self` block."
    )
    assert re.search(r"^\s+_[A-Za-z]\w*\s*:\s*\S", src, re.MULTILINE), (
        "Expected at least one backend-only state var (an annotated field whose "
        "name starts with '_') for the cancel flag / in-progress guard."
    )
    assert re.search(r"@rx\.var\b|rx\.var\s*\(", src), (
        "Expected at least one computed var declared with `@rx.var`."
    )
    assert "rx.foreach" in src or re.search(r"\bforeach\s*\(", src), (
        "Expected `rx.foreach` to render the per-record list."
    )
    assert "hash_core" in src or "hash_record" in src, (
        "The Reflex app must import and use the `hash_core` module."
    )


# ---------------------------------------------------------------------------
# Step 3 & 4: runtime checks against the live dev server
# ---------------------------------------------------------------------------
def test_backend_port_is_live(start_app):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        result = s.connect_ex((HOST, BACKEND_PORT))
    assert result == 0, (
        f"Expected the Reflex backend to be listening on {HOST}:{BACKEND_PORT}."
    )


def test_frontend_renders_app(start_app):
    resp = requests.get(BASE_URL + "/", timeout=30)
    assert resp.status_code == 200, (
        f"GET {BASE_URL}/ returned status {resp.status_code}, expected 200."
    )
    html = resp.text
    assert "File Hash Worker" in html, (
        "The rendered page must contain the heading text 'File Hash Worker'."
    )
    assert "Start" in html, "The rendered page must contain a 'Start' button label."
    assert "Cancel" in html, "The rendered page must contain a 'Cancel' button label."
