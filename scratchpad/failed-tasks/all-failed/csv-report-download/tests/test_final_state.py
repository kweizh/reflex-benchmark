import os
import socket

import pytest
import requests
from playwright.sync_api import sync_playwright
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/sales_report"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly to avoid IPv6 loopback (::1) resolution issues.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"

CSV_HEADER = "date,category,product,quantity,amount"

CATEGORY_GROUP = {"All Categories", "Books", "Clothing", "Electronics"}
DATE_GROUP = {"All Dates", "2024-01-15", "2024-01-16"}


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        return s.connect_ex((host, port)) == 0


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend :3000, backend :8000) via uv."""

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the frontend, which can take a while.
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            if not _port_open(HOST, BACKEND_PORT):
                return False
            if not _port_open(HOST, FRONTEND_PORT):
                return False
            try:
                resp = requests.get(BASE_URL, timeout=20)
                return resp.status_code < 500
            except requests.RequestException:
                return False

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
        print(f"===== [{tag}] reflex_app log begin =====")
        print("".join(new))
        print(f"===== [{tag}] reflex_app log end   =====")

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
def browser(start_app):
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        yield br
        br.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(accept_downloads=True)
    pg = context.new_page()
    yield pg
    context.close()


def _wait_hydrated(page):
    """Wait until the websocket has hydrated the page with seed data."""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    # Default view is All Categories / All Dates and includes this product.
    page.get_by_text("USB Cable").first.wait_for(timeout=90000)


def _set_filter(page, group: set[str], value: str):
    """Open the Radix select whose current value belongs to `group` and pick `value`."""
    triggers = page.get_by_role("combobox")
    count = triggers.count()
    assert count >= 2, f"Expected at least 2 dropdown selectors, found {count}."
    for i in range(count):
        trigger = triggers.nth(i)
        text = (trigger.inner_text() or "").strip()
        if text in group:
            trigger.click()
            page.get_by_role("option", name=value, exact=True).first.click()
            page.wait_for_timeout(800)
            return
    raise AssertionError(
        f"Could not find a dropdown currently showing one of {group}."
    )


def _export_csv(page) -> str:
    with page.expect_download(timeout=30000) as dl:
        page.get_by_role("button", name="Export CSV").first.click()
    download = dl.value
    path = download.path()
    assert path is not None, "No file was downloaded when clicking 'Export CSV'."
    with open(path, "rb") as f:
        raw = f.read()
    assert download.suggested_filename == "sales_report.csv", (
        f"Expected downloaded filename 'sales_report.csv', got "
        f"{download.suggested_filename!r}."
    )
    return raw.decode("utf-8")


def _csv_lines(content: str) -> list[str]:
    lines = [ln.rstrip("\r") for ln in content.split("\n")]
    return [ln for ln in lines if ln.strip() != ""]


def test_default_view_shows_all_rows(page):
    _wait_hydrated(page)
    body = page.inner_text("body")
    assert "530.00" in body, (
        f"Expected total 530.00 for the unfiltered report; body was:\n{body}"
    )
    assert "USB Cable" in body, "Expected 'USB Cable' row in the default report."
    assert "Web Dev" in body, "Expected 'Web Dev' row in the default report."


def test_filtered_view_books_on_date(page):
    _wait_hydrated(page)
    _set_filter(page, CATEGORY_GROUP, "Books")
    _set_filter(page, DATE_GROUP, "2024-01-16")
    page.get_by_text("SQL Guide").first.wait_for(timeout=30000)
    body = page.inner_text("body")
    assert "150.00" in body, (
        f"Expected total 150.00 for Books/2024-01-16; body was:\n{body}"
    )
    assert "SQL Guide" in body, "Expected 'SQL Guide' in the filtered report."
    assert "Web Dev" in body, "Expected 'Web Dev' in the filtered report."
    assert "USB Cable" not in body, (
        "Row 'USB Cable' should be filtered out for Books/2024-01-16."
    )


def test_empty_state(page):
    _wait_hydrated(page)
    _set_filter(page, CATEGORY_GROUP, "Clothing")
    _set_filter(page, DATE_GROUP, "2024-01-16")
    page.get_by_text("No sales match the selected filters.").first.wait_for(
        timeout=30000
    )
    body = page.inner_text("body")
    assert "No sales match the selected filters." in body, (
        "Expected the empty-state message for Clothing/2024-01-16."
    )
    assert "USB Cable" not in body, "No data rows should be shown in the empty state."


def test_csv_export_full_report(page):
    _wait_hydrated(page)
    content = _export_csv(page)
    lines = _csv_lines(content)
    assert lines[0] == CSV_HEADER, f"Unexpected CSV header: {lines[0]!r}"
    data_lines = lines[1:]
    assert len(data_lines) == 7, (
        f"Expected 7 data rows in the full CSV export, got {len(data_lines)}: {data_lines}"
    )
    assert data_lines[0] == "2024-01-15,Electronics,USB Cable,3,30.00", (
        f"Unexpected first data line: {data_lines[0]!r}"
    )
    assert data_lines[-1] == "2024-01-16,Books,Web Dev,3,90.00", (
        f"Unexpected last data line: {data_lines[-1]!r}"
    )
    expected = [
        "2024-01-15,Electronics,USB Cable,3,30.00",
        "2024-01-15,Electronics,Mouse,2,50.00",
        "2024-01-15,Books,Python 101,4,120.00",
        "2024-01-15,Clothing,T-Shirt,5,100.00",
        "2024-01-16,Electronics,Keyboard,1,80.00",
        "2024-01-16,Books,SQL Guide,2,60.00",
        "2024-01-16,Books,Web Dev,3,90.00",
    ]
    assert data_lines == expected, (
        f"Full CSV export did not match expected rows.\nGot:      {data_lines}\n"
        f"Expected: {expected}"
    )


def test_csv_export_filtered_report(page):
    _wait_hydrated(page)
    _set_filter(page, CATEGORY_GROUP, "Books")
    _set_filter(page, DATE_GROUP, "2024-01-16")
    page.get_by_text("SQL Guide").first.wait_for(timeout=30000)
    content = _export_csv(page)
    lines = _csv_lines(content)
    assert lines[0] == CSV_HEADER, f"Unexpected CSV header: {lines[0]!r}"
    data_lines = lines[1:]
    expected = [
        "2024-01-16,Books,SQL Guide,2,60.00",
        "2024-01-16,Books,Web Dev,3,90.00",
    ]
    assert data_lines == expected, (
        f"Filtered CSV export did not match expected rows.\nGot:      {data_lines}\n"
        f"Expected: {expected}"
    )
