import os
import socket
import subprocess
import time

import pytest
from xprocess import ProcessStarter

from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/myproject"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _kill_leftover_servers():
    """Best-effort kill of any leftover server holding ports 3000 or 8000."""
    for port in (FRONTEND_PORT, BACKEND_PORT):
        try:
            result = subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # fuser exits non-zero when no process is found; that is fine.
            _ = result
        except FileNotFoundError:
            # fuser may not be installed; ignore.
            pass
        except subprocess.TimeoutExpired:
            pass
    # Give the OS a moment to release the sockets.
    time.sleep(2)


@pytest.fixture(scope="session")
def start_reflex_app(xprocess):
    """Start the Reflex application for browser verification."""
    _kill_leftover_servers()

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run", "--env", "prod"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            return _port_open("localhost", FRONTEND_PORT) and _port_open(
                "localhost", BACKEND_PORT
            )

    xprocess.ensure(Starter.name, Starter)

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()
    _kill_leftover_servers()


@pytest.fixture(scope="session")
def browser_verifier():
    yield PochiVerifier()


def test_theme_selector_exposes_all_three_options(start_reflex_app, browser_verifier):
    reason = (
        "The user must be able to choose between light, dark, or auto on the theme "
        "selector, and the header must display the current selection."
    )
    truth = (
        "Navigate to http://localhost:3000/. Verify that the page exposes a theme "
        "selector control that offers three options named exactly 'light', 'dark', "
        "and 'auto'. Verify that the page header shows the current theme selection."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_theme_selector_exposes_all_three_options",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_selecting_dark_sets_cookie_to_dark(start_reflex_app, browser_verifier):
    reason = (
        "Selecting the dark theme must persist the choice in a cookie named "
        "theme_pref with value 'dark' and switch the effective theme to dark."
    )
    truth = (
        "Navigate to http://localhost:3000/. Use the theme selector to choose 'dark'. "
        "Open the browser storage inspector (Application/Storage > Cookies) for "
        "http://localhost:3000 and confirm that a cookie named exactly 'theme_pref' "
        "exists with value exactly 'dark'. Confirm the page header reports that the "
        "selected theme is 'dark' and that the effective theme is 'dark'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_selecting_dark_sets_cookie_to_dark",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_selecting_light_updates_cookie_and_palette(start_reflex_app, browser_verifier):
    reason = (
        "Selecting the light theme must update the cookie to 'light' and visibly "
        "switch the rendered palette to the light palette."
    )
    truth = (
        "Navigate to http://localhost:3000/. Use the theme selector to choose 'light'. "
        "Open the cookies for http://localhost:3000 and confirm that the cookie named "
        "'theme_pref' has value exactly 'light'. Confirm that the body background "
        "uses a clearly light palette (near-white background) and that the header "
        "now shows the light palette as well."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_selecting_light_updates_cookie_and_palette",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_auto_follows_simulated_system_preference(start_reflex_app, browser_verifier):
    reason = (
        "When theme is auto, the effective theme must follow the simulated OS "
        "preference, and the cookie must record the literal value 'auto'."
    )
    truth = (
        "Navigate to http://localhost:3000/. Use the theme selector to choose 'auto'. "
        "Confirm that the cookie 'theme_pref' on http://localhost:3000 has value "
        "exactly 'auto'. Click the control labeled 'Simulate system: dark' and "
        "confirm that the header now reports effective_theme as 'dark' and the body "
        "uses the dark palette. Then click 'Simulate system: light' and confirm "
        "that the header now reports effective_theme as 'light' and the body uses "
        "the light palette."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_auto_follows_simulated_system_preference",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_forced_themes_override_system_preference(start_reflex_app, browser_verifier):
    reason = (
        "Explicit light and dark selections must override the simulated OS "
        "preference and keep the effective theme fixed."
    )
    truth = (
        "Navigate to http://localhost:3000/. Use the theme selector to choose 'dark', "
        "then click 'Simulate system: light'. Confirm the header still reports "
        "effective_theme as 'dark' and the dark palette is still rendered. Next, use "
        "the theme selector to choose 'light' and click 'Simulate system: dark'. "
        "Confirm the header still reports effective_theme as 'light' and the light "
        "palette is still rendered."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_forced_themes_override_system_preference",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_palette_applied_on_every_page(start_reflex_app, browser_verifier):
    reason = (
        "Every page must derive its colors from the same palette so the theme is "
        "consistent across navigation."
    )
    truth = (
        "Navigate to http://localhost:3000/ and select theme 'dark'. Then navigate "
        "to http://localhost:3000/about. Confirm that both the header and the body "
        "of the /about page use the dark palette. Use the theme selector on /about "
        "(or navigate back to /) to switch the theme to 'light' and confirm that "
        "both http://localhost:3000/ and http://localhost:3000/about now render "
        "with the light palette."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_palette_applied_on_every_page",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_cookie_persists_after_reload(start_reflex_app, browser_verifier):
    reason = (
        "The cookie-backed theme preference must survive a full page reload so the "
        "user's choice is restored on the next visit."
    )
    truth = (
        "Navigate to http://localhost:3000/. Use the theme selector to choose 'dark'. "
        "Perform a hard reload of the page (e.g. via Ctrl/Cmd+Shift+R). After the "
        "reload, confirm that the theme selector still shows 'dark' as the active "
        "selection, that the header still reports effective_theme as 'dark', that "
        "the dark palette is still rendered, and that the cookie 'theme_pref' on "
        "http://localhost:3000 still exists with value exactly 'dark'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_cookie_persists_after_reload",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
