import os
import re
import socket
import subprocess
from urllib.parse import urljoin

import pytest
import requests
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/role_guard"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Bind/connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) on some stacks, so the dev server would listen on ::1 only while an
# AF_INET socket to 127.0.0.1 never connects -> the readiness check would hang.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"

# Seeded accounts, defined by the task description.
ADMIN_USER = "admin"
ADMIN_PW = "s3cure-admin-pw"
REGULAR_USER = "alice"
REGULAR_PW = "s3cure-user-pw"
PLAINTEXT_SECRETS = [ADMIN_PW, REGULAR_PW]


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend :3000, backend :8000) via `uv run reflex run`."""

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        env = os.environ.copy()
        env["REFLEX_TELEMETRY_ENABLED"] = "false"
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # The very first `reflex run` installs the JS toolchain and compiles the
        # Next.js frontend, which can take several minutes.
        timeout = 900
        terminate_on_interrupt = True

        def startup_check(self):
            # Frontend must be accepting connections.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
            # Backend (websocket/event server) must also be up.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, BACKEND_PORT)) != 0:
                    return False
            try:
                resp = requests.get(BASE_URL + "/login", timeout=30)
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
            return
        new_lines = all_lines[printed_log_lines:]
        skipped = printed_log_lines
        printed_log_lines = len(all_lines)
        print(f"===================== [{tag}: Begin] {Starter.name} logfile =====================")
        if skipped > 0:
            print(f"(skipped {skipped} already-printed lines)")
        print("".join(new_lines))
        print(f"===================== [{tag}: End  ] {Starter.name} logfile =====================")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_unauthenticated_guards_redirect_to_login(start_app, browser_verifier):
    reason = (
        "Protected pages use on_load event guards that must redirect unauthenticated "
        "visitors to the login page."
    )
    truth = (
        f"Open a fresh browser and navigate to {BASE_URL}/dashboard . "
        "Because no user is logged in, the on_load guard must redirect the browser to the "
        "login page, so the final URL path ends with '/login' and the word 'Dashboard' is "
        f"NOT shown as page content. Then navigate to {BASE_URL}/admin . Again, because no "
        "user is logged in, the browser must be redirected to the login page (final URL path "
        "ends with '/login') and the text 'Admin Panel' is NOT shown. "
        "Pass only if both unauthenticated navigations end on the login page."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_unauthenticated_guards",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_invalid_login_is_rejected(start_app, browser_verifier):
    reason = "Invalid credentials must be rejected locally and show an error, without granting access."
    truth = (
        f"Open a fresh browser and navigate to {BASE_URL}/login . Type the username "
        f"'{ADMIN_USER}' into the username field and the password 'wrong-pw' into the password "
        "field, then submit the login form. The login must be rejected: the page must stay on "
        "the login route (URL path ends with '/login') and must display an error message that "
        "contains the text 'Invalid credentials'. The browser must NOT be redirected to the "
        "dashboard. Pass only if the error is shown and no dashboard access is granted."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_invalid_login",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_regular_user_login_and_admin_blocked(start_app, browser_verifier):
    reason = (
        "A regular (non-admin) user can reach the dashboard but must be blocked from the "
        "admin-only page and sent to the forbidden page."
    )
    truth = (
        f"Open a fresh browser and navigate to {BASE_URL}/login . Log in with username "
        f"'{REGULAR_USER}' and password '{REGULAR_PW}' by filling in the form and submitting it. "
        "After a successful login the browser must be redirected to the dashboard (URL path ends "
        "with '/dashboard') and the page must show the text 'Dashboard', the username 'alice', and "
        f"the role 'user'. Next, while still logged in as this user, navigate to {BASE_URL}/admin . "
        "Because this user is not an admin, the on_load guard must redirect the browser to the "
        "forbidden page (URL path ends with '/forbidden') which shows the text 'Access Denied'; the "
        "text 'Admin Panel' must NOT be shown. Pass only if the dashboard shows the correct user "
        "and role AND the admin page is blocked with the forbidden page."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_regular_user_flow",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_admin_can_access_admin_page(start_app, browser_verifier):
    reason = "An admin user must be able to log in and view the admin-only page."
    truth = (
        f"Open a fresh browser and navigate to {BASE_URL}/login . Log in with username "
        f"'{ADMIN_USER}' and password '{ADMIN_PW}' by filling in the form and submitting it. "
        "After a successful login the browser must be redirected to the dashboard (URL path ends "
        f"with '/dashboard'). Then navigate to {BASE_URL}/admin . Because this user is an admin, the "
        "admin page must render and display the text 'Admin Panel' (the browser must NOT be "
        "redirected to '/login' or '/forbidden'). Pass only if the admin page shows 'Admin Panel'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_admin_flow",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_logout_clears_session(start_app, browser_verifier):
    reason = "Logging out must clear the session so protected pages guard again."
    truth = (
        f"Open a fresh browser and navigate to {BASE_URL}/login . Log in with username "
        f"'{ADMIN_USER}' and password '{ADMIN_PW}'. After being redirected to the dashboard, use the "
        "logout control on the dashboard. Logging out must return the browser to the login page "
        f"(URL path ends with '/login'). Then, in the same browser, navigate to {BASE_URL}/dashboard . "
        "Because the session was cleared, the on_load guard must redirect the browser back to the "
        "login page (URL path ends with '/login') and 'Dashboard' content must NOT be shown. Pass "
        "only if logout returns to login AND the dashboard is guarded afterwards."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_logout",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_plaintext_secrets_not_exposed_in_frontend(start_app):
    """The seeded plaintext passwords must never be embedded in the served frontend assets."""
    login_url = BASE_URL + "/login"
    resp = requests.get(login_url, timeout=30)
    assert resp.status_code < 500, f"GET {login_url} failed with status {resp.status_code}"

    combined = resp.text

    # Fetch one level of referenced scripts from the login page and include them
    # in the search, since backend-only secrets must not appear anywhere client-side.
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', resp.text)
    for src in script_srcs:
        asset_url = urljoin(login_url + "/", src)
        try:
            asset_resp = requests.get(asset_url, timeout=30)
        except requests.RequestException:
            continue
        if asset_resp.status_code < 400:
            combined += "\n" + asset_resp.text

    for secret in PLAINTEXT_SECRETS:
        assert secret not in combined, (
            f"Plaintext password '{secret}' was found in the served frontend assets. "
            "Credentials must be stored on the backend only and never sent to the client."
        )
