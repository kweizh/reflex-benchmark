import os
import re
import socket
import stat
import subprocess

import pytest

PROJECT_DIR = "/home/user/myproject"
DEPLOY_SCRIPT = os.path.join(PROJECT_DIR, "deploy.sh")
DEPLOY_LOG = os.path.join(PROJECT_DIR, "deploy.log")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
RXCONFIG_FILE = os.path.join(PROJECT_DIR, "rxconfig.py")


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def test_rxconfig_exists():
    assert os.path.isfile(RXCONFIG_FILE), (
        f"Expected rxconfig.py at {RXCONFIG_FILE}; the agent must run `reflex init --template blank` in the project."
    )


def test_requirements_txt_contains_reflex():
    assert os.path.isfile(REQUIREMENTS_FILE), (
        f"Expected requirements.txt at {REQUIREMENTS_FILE}; create it with `uv pip freeze > requirements.txt`."
    )
    with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as fh:
        lines = [line.strip() for line in fh.readlines()]
    # Match a top-level `reflex` package line, not `reflex-<something>` siblings.
    reflex_pattern = re.compile(r"^reflex(\s|$|[<>=~!@;\[].*)", re.IGNORECASE)
    matched = [line for line in lines if reflex_pattern.match(line)]
    assert matched, (
        f"requirements.txt does not contain a top-level `reflex` dependency line. Lines were: {lines}"
    )


def test_deploy_script_exists_and_executable():
    assert os.path.isfile(DEPLOY_SCRIPT), (
        f"Expected deploy script at {DEPLOY_SCRIPT}."
    )
    mode = os.stat(DEPLOY_SCRIPT).st_mode
    assert bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)), (
        f"{DEPLOY_SCRIPT} exists but is not marked executable; run `chmod +x deploy.sh`."
    )


def test_deploy_script_uses_env_vars():
    with open(DEPLOY_SCRIPT, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert "REFLEX_CLOUD_TOKEN" in content, (
        "deploy.sh must reference REFLEX_CLOUD_TOKEN from the environment instead of hard-coding it."
    )
    assert "REFLEX_CLOUD_PROJECT_ID" in content, (
        "deploy.sh must reference REFLEX_CLOUD_PROJECT_ID from the environment instead of hard-coding it."
    )


def test_deploy_log_records_app_name():
    assert os.path.isfile(DEPLOY_LOG), (
        f"Expected deploy log at {DEPLOY_LOG} after running deploy.sh."
    )
    with open(DEPLOY_LOG, "r", encoding="utf-8") as fh:
        log_content = fh.read()
    match = re.search(r"Deployed app:\s*(\S+)", log_content)
    assert match, (
        "deploy.log must contain a line in the format `Deployed app: <app_name>`."
    )
    assert match.group(1), "Deployed app name in deploy.log is empty."


def test_reflex_cloud_apps_list_returns_at_least_one_app():
    token = os.environ.get("REFLEX_CLOUD_TOKEN", "")
    project_id = os.environ.get("REFLEX_CLOUD_PROJECT_ID", "")
    assert token, "REFLEX_CLOUD_TOKEN must be set in the verifier environment."
    assert project_id, "REFLEX_CLOUD_PROJECT_ID must be set in the verifier environment."

    result = subprocess.run(
        [
            "uv",
            "run",
            "reflex",
            "cloud",
            "apps",
            "list",
            "--project",
            project_id,
            "--token",
            token,
            "--no-interactive",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"'reflex cloud apps list' failed (exit {result.returncode}). "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    stdout = result.stdout
    # The CLI prints a table; verify it has more than just a header / empty body.
    # Strategy: count non-empty lines that look like a data row (not pure borders, not header words).
    candidate_rows = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Skip ASCII / unicode table border lines like "----", "====", "┃━━━" etc.
        if re.fullmatch(r"[\s\-\=\+_\|\u2500-\u257F]+", line):
            continue
        # Skip the header row that contains common header column words.
        lowered = line.lower()
        if re.search(r"\bapp[\s_-]?name\b", lowered) and ("id" in lowered or "status" in lowered or "region" in lowered):
            continue
        candidate_rows.append(line)

    assert candidate_rows, (
        "`reflex cloud apps list` returned no deployment rows. "
        f"stdout was:\n{stdout}"
    )


def test_reflex_dev_ports_are_free():
    # The deploy flow may have started a Reflex dev server. The agent must kill
    # any such server before finishing the task.
    for port in (3000, 8000):
        assert not _port_in_use("127.0.0.1", port), (
            f"Port {port} is still in use after deploy; the agent must kill the Reflex frontend/backend before finishing."
        )
