import datetime
import os
import socket
import sqlite3

import pytest
import requests
from xprocess import ProcessStarter

from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/pomodoro_timer"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")

FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly. `localhost` may resolve to the IPv6 loopback
# (::1) while the dev server listens on 0.0.0.0 / 127.0.0.1, which would make
# readiness checks hang until timeout.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        return s.connect_ex((HOST, port)) == 0


def _clear_session_rows():
    """Best-effort: remove existing rows so today's counts are deterministic.

    We only delete rows here; we never create the schema. If the table is
    missing it means the app never created it, which is verified as a failure
    by the dedicated database test.
    """
    if not os.path.isfile(DB_PATH):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM pomodoro_session")
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        pass


def _today_work_rows():
    """Return list of (phase, duration_seconds) rows logged with today's date."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT phase, duration_seconds, completed_at FROM pomodoro_session"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    today = datetime.date.today().isoformat()
    result = []
    for r in rows:
        completed_at = str(r["completed_at"])
        if completed_at.startswith(today):
            result.append((str(r["phase"]), r["duration_seconds"]))
    return result


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend on 3000, backend on 8000)."""
    _clear_session_rows()

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        # CRITICAL: set env as a class attribute, never inside popen_kwargs.
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open(FRONTEND_PORT):
                return False
            if not _port_open(BACKEND_PORT):
                return False
            # The first request triggers on-demand bundling; allow ample time.
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
        skipped = printed_log_lines
        printed_log_lines = len(all_lines)
        print(f"===================== [{tag}: Begin] reflex_app logfile =====================")
        if skipped > 0:
            print(f"(skipped {skipped} already-printed lines)")
        print("".join(new_lines))
        print(f"===================== [{tag}: End  ] reflex_app logfile =====================")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_initial_render(start_app, browser_verifier):
    reason = (
        "On first load the Pomodoro timer must start in the Work phase with the "
        "full work time remaining, not yet running, and expose Start/Pause/Reset "
        "controls."
    )
    truth = (
        f"Navigate to {BASE_URL}. Do NOT click any button. "
        "Verify the page shows the text 'Phase: Work'. "
        "Verify the countdown timer shows '00:05'. "
        "Verify the text 'Completed: 0' is visible. "
        "Verify three buttons labeled exactly 'Start', 'Pause', and 'Reset' are "
        "visible on the page."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_initial_render",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_start_is_idempotent(start_app, browser_verifier):
    reason = (
        "Pressing Start repeatedly must not spawn multiple concurrent tick loops; "
        "the timer must never count down faster than one second per real second."
    )
    truth = (
        f"Navigate to {BASE_URL}. The page should show 'Phase: Work' and '00:05'. "
        "Click the 'Start' button, then immediately click the 'Start' button a "
        "second time. Watch the countdown timer for about 3 seconds. "
        "Verify the timer decreases at a rate of about one second per real second "
        "(after roughly 3 seconds it should read about '00:02'). "
        "PASS only if the countdown does NOT run faster than one second per second "
        "(it must NOT drop by 2 or more seconds within a single real second)."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_start_is_idempotent",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_countdown_phase_transition_and_counter(start_app, browser_verifier):
    reason = (
        "While running the timer counts down once per second. When the Work phase "
        "reaches zero it must increment the completed-sessions counter and switch "
        "to the Break phase, and when the Break phase reaches zero it must switch "
        "back to the Work phase, continuing automatically."
    )
    truth = (
        f"Navigate to {BASE_URL}. Verify it shows 'Phase: Work' and '00:05'. "
        "Click the 'Start' button. Verify that within about 2 seconds the timer "
        "value becomes smaller than '00:05' (it is counting down). "
        "Keep watching for up to about 10 seconds: when the Work timer reaches "
        "'00:00', verify the display switches to 'Phase: Break' showing about "
        "'00:03' AND the counter now shows 'Completed: 1'. "
        "Continue watching: when the Break timer reaches '00:00', verify the "
        "display switches back to 'Phase: Work' showing '00:05'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_countdown_phase_transition_and_counter",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_pause_stops_countdown(start_app, browser_verifier):
    reason = (
        "Pause must stop the countdown while keeping the current phase and "
        "remaining time."
    )
    truth = (
        f"Navigate to {BASE_URL}. Click the 'Start' button. Wait about 2 seconds so "
        "the timer is counting down below '00:05'. Click the 'Pause' button. "
        "Note the timer value shown right after pausing, then wait about 3 seconds. "
        "Verify the timer value does NOT change at all while paused (it stays the "
        "same for the entire 3 seconds)."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_pause_stops_countdown",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_reset_returns_to_work(start_app, browser_verifier):
    reason = (
        "Reset must stop the countdown, return to the Work phase, and restore the "
        "full work time."
    )
    truth = (
        f"Navigate to {BASE_URL}. Click the 'Start' button. Wait about 2 seconds. "
        "Click the 'Reset' button. Verify the display returns to 'Phase: Work' with "
        "the timer showing '00:05'. Wait about 2 more seconds and verify the timer "
        "stays at '00:05' (it is stopped and not counting down)."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_reset_returns_to_work",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_completed_work_sessions_logged_to_db(start_app, browser_verifier):
    # Drive exactly one completed Work session in a fresh browser session.
    reason = (
        "Every completed Work session must be persisted as a row in the local "
        "SQLite database."
    )
    drive_truth = (
        f"Navigate to {BASE_URL}. Verify it shows 'Phase: Work' and '00:05'. "
        "Click the 'Start' button. Wait until the timer counts down from '00:05' to "
        "'00:00' and the display switches to 'Phase: Break'. Verify the counter now "
        "shows 'Completed: 1'."
    )
    drive = browser_verifier.verify(
        reason=reason,
        truth=drive_truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_db_drive_completion",
    )
    assert drive.status == "pass", (
        f"Failed to drive a completed Work session in the browser: {drive.reason}"
    )

    assert os.path.isfile(DB_PATH), (
        f"Expected the app's SQLite database at {DB_PATH}, but it does not exist."
    )

    rows = _today_work_rows()
    work_rows = [r for r in rows if r[0] == "work"]
    assert len(work_rows) >= 1, (
        "Expected at least one completed Work session logged in table "
        f"'pomodoro_session' for today, but found rows: {rows}"
    )
    assert any(int(dur) == 5 for _, dur in work_rows), (
        "Expected a logged work session with duration_seconds == 5, but found "
        f"durations: {[dur for _, dur in work_rows]}"
    )

    # The 'Today' stat on the page must reflect the number of rows logged today.
    today_count = len(work_rows)
    stat_truth = (
        f"Navigate to {BASE_URL}. Do NOT click any button. "
        f"Verify the page shows the text 'Today: {today_count}'."
    )
    stat = browser_verifier.verify(
        reason=(
            "A computed var must derive today's completed-session count from the "
            "database and display it on the page."
        ),
        truth=stat_truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_db_today_stat",
    )
    assert stat.status == "pass", (
        f"'Today' stat did not match the database row count ({today_count}): "
        f"{stat.reason}"
    )
