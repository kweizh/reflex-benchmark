import json
import os
import socket
import sqlite3
import subprocess

import pytest
import requests
from pochi_verifier import PochiVerifier
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/dynamic_form_builder"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly. `localhost` may resolve to the IPv6 loopback (::1),
# while the dev server may only listen on the IPv4 loopback, causing readiness
# checks to hang for the full timeout.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


def _reset_database():
    """Ensure the `submission` table exists and contains no rows before the flow.

    Reflex does not auto-create tables, so the app author must have generated
    migrations. Applying them here is idempotent and guarantees the schema is
    present; we then clear any existing rows so the persistence checks are
    deterministic.
    """
    migrate = subprocess.run(
        ["uv", "run", "reflex", "db", "migrate"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env={**os.environ, "REFLEX_TELEMETRY_ENABLED": "false"},
    )
    print("=== reflex db migrate stdout ===")
    print(migrate.stdout)
    print("=== reflex db migrate stderr ===")
    print(migrate.stderr)
    if os.path.isfile(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM submission")
            conn.commit()
            conn.close()
        except sqlite3.OperationalError as exc:
            # Table may not exist yet; the persistence tests will report a clear
            # failure if the app never created it.
            print(f"Could not clear submission table (may not exist yet): {exc}")


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend :3000, backend :8000) with uv."""
    _reset_database()

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        env = {**os.environ, "REFLEX_TELEMETRY_ENABLED": "false"}
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the frontend and installs JS deps, which is slow.
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend must be up.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, BACKEND_PORT)) != 0:
                    return False
            # Frontend must accept connections.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
            # The first request triggers on-demand bundling; allow ample time.
            try:
                resp = requests.get(BASE_URL, timeout=60)
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
        skipped = printed_log_lines
        printed_log_lines = len(all_lines)
        print(f"===================== [{tag}: Begin] {Starter.name} log =====================")
        if skipped > 0:
            print(f"(skipped {skipped} already-printed lines)")
        print("".join(new_lines))
        print(f"===================== [{tag}: End  ] {Starter.name} log =====================")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


@pytest.fixture(scope="session")
def ui_flow(start_app, browser_verifier):
    """Drive the full builder journey once with the browser agent."""
    reason = (
        "The app is a dynamic form builder. Users add field definitions (label + "
        "type text/number/select), toggle whether a field is required, reorder and "
        "remove fields, see a live preview whose widgets depend on the field type, "
        "see a reactive field count and validity status, and submit valid forms "
        "which are persisted."
    )
    truth = (
        f"Navigate to {BASE_URL}. "
        "Verify the page shows the heading text 'Dynamic Form Builder', the text "
        "'Fields: 0', and the text 'Status: valid'. "
        "Step 1: In the builder, type 'Full Name' into the input whose placeholder is "
        "'New field label', set the field type selector to 'text', then click the "
        "'Add Field' button. Then turn ON the required checkbox on the 'Full Name' row. "
        "Verify the page now shows 'Fields: 1', that the preview contains an input "
        "whose placeholder is 'Full Name', and that the status text is now "
        "'Status: invalid'. "
        "Step 2: Type 'Age' into the 'New field label' input, set the type selector to "
        "'number', and click 'Add Field'. Verify the page shows 'Fields: 2' and the "
        "preview contains an input whose placeholder is 'Age'. "
        "Step 3: Type 'Country' into the 'New field label' input, set the type selector "
        "to 'select', and click 'Add Field'. Verify the page shows 'Fields: 3' and the "
        "preview now contains a dropdown/combobox for the 'Country' field. "
        "Step 4: Click the 'Up' control on the 'Age' field row so the field order "
        "becomes: Age, then Full Name, then Country. "
        "Step 5: Click the 'Submit' button WITHOUT filling any values. Verify a visible "
        "message containing the text 'Please fill required fields' appears. "
        "Step 6: Fill the preview input whose placeholder is 'Full Name' with the value "
        "'Alice', and fill the preview input whose placeholder is 'Age' with the value "
        "'30'. Verify the status text changes to 'Status: valid'. "
        "Step 7: Click the 'Submit' button again. Verify a visible message containing "
        "the text 'Saved' appears. "
        "Step 8: Click the 'Remove' control on the 'Country' field row. Verify the page "
        "shows 'Fields: 2' and the 'Country' dropdown/combobox is no longer present in "
        "the preview."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_ui_flow",
    )
    return result


def test_ui_journey(ui_flow):
    assert ui_flow.status == "pass", f"Browser verification failed: {ui_flow.reason}"


def test_submission_persisted(ui_flow):
    """Exactly one row must be persisted (the single valid submit)."""
    assert os.path.isfile(DB_PATH), f"SQLite database not found at {DB_PATH}."
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM submission")
        count = cur.fetchone()[0]
    finally:
        conn.close()
    # If the invalid submit had persisted a row there would be two rows total.
    assert count == 1, (
        f"Expected exactly 1 row in the 'submission' table (one valid submit; the "
        f"invalid submit must not persist), but found {count}."
    )


def test_submission_schema_and_values(ui_flow):
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT schema_json, values_json FROM submission ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "No row found in the 'submission' table."
    schema_raw, values_raw = row

    schema = json.loads(schema_raw)
    assert isinstance(schema, list), f"schema_json must be a JSON array, got: {schema_raw}"
    assert len(schema) == 3, f"Expected 3 field definitions in schema_json, got: {schema}"

    for elem in schema:
        assert set(elem.keys()) == {"label", "type", "required"}, (
            f"Each schema element must have exactly keys label/type/required, got: {elem}"
        )

    # Order must reflect the reorder: Age, Full Name, Country.
    labels = [e["label"] for e in schema]
    assert labels == ["Age", "Full Name", "Country"], (
        f"Expected field order ['Age', 'Full Name', 'Country'] after reordering, got: {labels}"
    )

    types = {e["label"]: e["type"] for e in schema}
    assert types["Age"] == "number", f"'Age' should have type 'number', got: {types['Age']}"
    assert types["Full Name"] == "text", f"'Full Name' should have type 'text', got: {types['Full Name']}"
    assert types["Country"] == "select", f"'Country' should have type 'select', got: {types['Country']}"

    required = {e["label"]: bool(e["required"]) for e in schema}
    assert required["Full Name"] is True, "'Full Name' should be marked required."
    assert required["Age"] is False, "'Age' should not be required."
    assert required["Country"] is False, "'Country' should not be required."

    values = json.loads(values_raw)
    assert isinstance(values, dict), f"values_json must be a JSON object, got: {values_raw}"
    assert values.get("Full Name") == "Alice", (
        f"Expected values_json['Full Name'] == 'Alice', got: {values.get('Full Name')}"
    )
    assert values.get("Age") == "30", (
        f"Expected values_json['Age'] == '30', got: {values.get('Age')}"
    )
