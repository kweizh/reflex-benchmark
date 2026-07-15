import os
import socket

import pytest
import requests
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/financial_ledger"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) while the dev server listens on 127.0.0.1 only, which would make the
# readiness check hang for the full timeout.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend :3000, backend :8000) via uv."""

    class Starter(ProcessStarter):
        name = "reflex_app"
        # Start the Reflex app with uv, as required by the task.
        args = ["uv", "run", "reflex", "run"]
        # CRITICAL: set `env` as a class attribute, NEVER inside popen_kwargs.
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the frontend and may install node/bun assets, which
        # can take several minutes.
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend must be up first (websocket state sync happens here).
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, BACKEND_PORT)) != 0:
                    return False
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
        except FileNotFoundError:
            all_lines = []
        new_lines = all_lines[printed_log_lines:]
        skipped = printed_log_lines
        printed_log_lines = len(all_lines)
        print(f"===== [{tag}: Begin] {Starter.name} logfile =====")
        if skipped > 0:
            print(f"(skipped {skipped} already-printed lines)")
        print("".join(new_lines))
        print(f"===== [{tag}: End] {Starter.name} logfile =====")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_initial_ledger_report(start_app, browser_verifier):
    """Verify serialized amounts/timestamps, running balances, and totals."""
    reason = (
        "The financial ledger report stores decimal.Decimal amounts and "
        "datetime timestamps in state and uses custom serializers plus computed "
        "vars to render a table with a running balance and totals. The seeded "
        "data must render with the exact currency and datetime formatting."
    )
    truth = (
        f"Navigate to {BASE_URL} and wait until the ledger table is populated "
        "with data (four seeded rows must appear; do not judge before the table "
        "has data). "
        "Verify the table shows these amounts formatted exactly as: "
        "'$1,000.00', '-$234.56', '$2,500.00', and '-$89.99'. "
        "Verify the table shows these timestamps formatted exactly as: "
        "'2024-01-01 09:00', '2024-01-02 14:30', '2024-01-05 08:00', and "
        "'2024-01-10 16:45'. "
        "Verify the running Balance column shows the cumulative balances in "
        "order: '$1,000.00', '$765.44', '$3,265.44', and '$3,175.45'. "
        "Verify the totals shown on the page are: Total credits '$3,500.00', "
        "Total debits '$324.55', and Net balance '$3,175.45'. "
        "The verification passes only if every one of these formatted values is "
        "present on the page."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_initial_ledger_report",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_add_entry_updates_report(start_app, browser_verifier):
    """Verify the add-entry event handler updates balance and totals."""
    reason = (
        "Adding a ledger entry must parse the amount into a Decimal, append a "
        "new row with the current timestamp, and reactively update the running "
        "balance and computed totals."
    )
    truth = (
        f"Navigate to {BASE_URL} and wait until the seeded ledger table is "
        "populated. Type 'Refund' into the description input and '50.25' into "
        "the amount input, then click the button that adds a new entry. "
        "After the update, verify that a new row appears whose amount is "
        "'$50.25' and whose running Balance is '$3,225.70'. "
        "Verify the Net balance total updates to '$3,225.70' and the Total "
        "credits total updates to '$3,550.25', while Total debits remains "
        "'$324.55'. The verification passes only if all of these updated values "
        "are present."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_add_entry_updates_report",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
