import os
import socket

import pytest
import requests
from pochi_verifier import PochiVerifier
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/employee_grid"
# Bind/connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) on some stacks, so a server listening only on 127.0.0.1 would never accept
# the connection and readiness checks would hang until timeout.
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
API_URL = f"{BACKEND_URL}/api/employees"

ROW_KEYS = {"id", "name", "department", "salary", "active"}
RESPONSE_KEYS = {"page", "page_size", "total", "total_pages", "page_label", "rows"}
DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Support"]


def expected_employees():
    """Reconstruct the deterministic seed dataset from the task specification."""
    employees = []
    for i in range(1, 25):
        employees.append(
            {
                "id": i,
                "name": f"Employee {i:02d}",
                "department": DEPARTMENTS[(i - 1) % 4],
                "salary": 50000 + ((i * 37) % 100) * 100,
                "active": (i % 5 != 0),
            }
        )
    return employees


def _port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend on 3000, backend on 8000)."""

    class Starter(ProcessStarter):
        name = "reflex_app"
        # Run the Reflex dev server through uv so the project's managed environment
        # (which contains reflex + aiosqlite) is used. The system python has no reflex.
        args = ["uv", "run", "reflex", "run"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # Reflex compiles the Next.js frontend on first run, which can be slow.
        timeout = 600
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend must answer the reserved health route with "pong".
            if not _port_open(HOST, BACKEND_PORT):
                return False
            try:
                ping = requests.get(f"{BACKEND_URL}/ping/", timeout=20)
                if ping.status_code != 200 or "pong" not in ping.text.lower():
                    return False
            except requests.RequestException:
                return False
            # Frontend must also be serving pages for the browser check.
            if not _port_open(HOST, FRONTEND_PORT):
                return False
            try:
                resp = requests.get(FRONTEND_URL, timeout=30)
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


def _get(params=None):
    resp = requests.get(API_URL, params=params, timeout=30)
    return resp


def test_backend_health(start_app):
    resp = requests.get(f"{BACKEND_URL}/ping/", timeout=30)
    assert resp.status_code == 200, f"/ping/ returned status {resp.status_code}"
    assert "pong" in resp.text.lower(), f"/ping/ did not return 'pong', got: {resp.text!r}"


def test_default_listing_shape_and_order(start_app):
    resp = _get()
    assert resp.status_code == 200, f"GET /api/employees returned {resp.status_code}"
    data = resp.json()
    assert set(data.keys()) == RESPONSE_KEYS, (
        f"Response keys must be exactly {RESPONSE_KEYS}, got {set(data.keys())}"
    )
    assert data["total"] == 24, f"Expected total 24, got {data['total']}"
    assert data["page"] == 1, f"Expected default page 1, got {data['page']}"
    assert data["page_size"] == 10, f"Expected default page_size 10, got {data['page_size']}"
    assert data["total_pages"] == 3, f"Expected total_pages 3, got {data['total_pages']}"
    assert data["page_label"] == "Page 1 of 3", (
        f"Expected page_label 'Page 1 of 3', got {data['page_label']!r}"
    )
    rows = data["rows"]
    assert len(rows) == 10, f"Default page should have 10 rows, got {len(rows)}"

    expected = expected_employees()
    for idx, row in enumerate(rows):
        assert set(row.keys()) == ROW_KEYS, (
            f"Row {idx} keys must be exactly {ROW_KEYS}, got {set(row.keys())}"
        )
        exp = expected[idx]  # default order is id ascending == reconstruction order
        assert row["id"] == exp["id"], f"Row {idx} id mismatch: {row['id']} != {exp['id']}"
        assert row["name"] == exp["name"], f"Row {idx} name mismatch: {row['name']!r}"
        assert row["department"] == exp["department"], (
            f"Row {idx} department mismatch: {row['department']!r}"
        )
        assert row["salary"] == exp["salary"], (
            f"Row {idx} salary mismatch: {row['salary']} != {exp['salary']}"
        )
        assert bool(row["active"]) == exp["active"], (
            f"Row {idx} active mismatch: {row['active']} != {exp['active']}"
        )


def test_pagination_last_page(start_app):
    resp = _get({"page": 3, "page_size": 10})
    assert resp.status_code == 200, f"Pagination request returned {resp.status_code}"
    data = resp.json()
    assert data["page_label"] == "Page 3 of 3", (
        f"Expected page_label 'Page 3 of 3', got {data['page_label']!r}"
    )
    rows = data["rows"]
    assert len(rows) == 4, f"Last page should have 4 rows, got {len(rows)}"
    ids = [r["id"] for r in rows]
    assert ids == [21, 22, 23, 24], f"Last page ids should be [21,22,23,24], got {ids}"


def test_department_filter(start_app):
    resp = _get({"department": "Engineering", "page_size": 100})
    assert resp.status_code == 200, f"Department filter returned {resp.status_code}"
    data = resp.json()
    expected = [e for e in expected_employees() if e["department"] == "Engineering"]
    assert data["total"] == len(expected), (
        f"Engineering total should be {len(expected)}, got {data['total']}"
    )
    assert data["total_pages"] == 1, f"Expected total_pages 1, got {data['total_pages']}"
    for row in data["rows"]:
        assert row["department"] == "Engineering", (
            f"Filtered row has wrong department: {row['department']!r}"
        )


def test_min_salary_filter(start_app):
    salaries = sorted(e["salary"] for e in expected_employees())
    threshold = salaries[len(salaries) // 2]  # median-ish value derived from the data
    resp = _get({"min_salary": threshold, "page_size": 100})
    assert resp.status_code == 200, f"min_salary filter returned {resp.status_code}"
    data = resp.json()
    expected_count = sum(1 for e in expected_employees() if e["salary"] >= threshold)
    assert data["total"] == expected_count, (
        f"min_salary={threshold} total should be {expected_count}, got {data['total']}"
    )
    for row in data["rows"]:
        assert row["salary"] >= threshold, (
            f"Row salary {row['salary']} is below min_salary {threshold}"
        )


def test_name_contains_filter(start_app):
    resp = _get({"name_contains": "1", "page_size": 100})
    assert resp.status_code == 200, f"name_contains filter returned {resp.status_code}"
    data = resp.json()
    expected_count = sum(1 for e in expected_employees() if "1" in e["name"])
    assert data["total"] == expected_count, (
        f"name_contains='1' total should be {expected_count}, got {data['total']}"
    )
    for row in data["rows"]:
        assert "1" in row["name"], f"Row name {row['name']!r} does not contain '1'"


def test_multi_column_sort(start_app):
    resp = _get({"sort": "department:asc,salary:desc", "page_size": 100})
    assert resp.status_code == 200, f"Multi-column sort returned {resp.status_code}"
    data = resp.json()
    rows = data["rows"]
    assert len(rows) == 24, f"Expected all 24 rows, got {len(rows)}"

    expected_order = sorted(
        expected_employees(), key=lambda e: (e["department"], -e["salary"])
    )
    expected_ids = [e["id"] for e in expected_order]
    actual_ids = [r["id"] for r in rows]
    assert actual_ids == expected_ids, (
        f"Multi-column sort order mismatch.\nExpected ids: {expected_ids}\nActual ids:   {actual_ids}"
    )

    # departments must be in ascending order overall
    dept_seq = [r["department"] for r in rows]
    assert dept_seq == sorted(dept_seq), (
        f"Departments are not in ascending order: {dept_seq}"
    )
    # within each department, salaries must be strictly descending
    from itertools import groupby

    for dept, group in groupby(rows, key=lambda r: r["department"]):
        sals = [r["salary"] for r in group]
        assert sals == sorted(sals, reverse=True) and len(set(sals)) == len(sals), (
            f"Salaries within department {dept!r} are not strictly descending: {sals}"
        )


def test_single_column_sort_salary_desc(start_app):
    resp = _get({"sort": "salary:desc"})
    assert resp.status_code == 200, f"salary:desc sort returned {resp.status_code}"
    data = resp.json()
    max_salary_emp = max(expected_employees(), key=lambda e: e["salary"])
    first = data["rows"][0]
    assert first["salary"] == max_salary_emp["salary"], (
        f"First row salary should be max {max_salary_emp['salary']}, got {first['salary']}"
    )
    assert first["id"] == max_salary_emp["id"], (
        f"First row id should be {max_salary_emp['id']}, got {first['id']}"
    )


def test_browser_grid_renders(start_app, browser_verifier):
    reason = (
        "The Reflex application's home page must render a server-side employee data "
        "grid showing employee rows, department values, sortable column headers, and a "
        "computed page label."
    )
    truth = (
        f"Navigate to {FRONTEND_URL}. Verify the page shows a table of employees "
        "containing rows with names like 'Employee 01' and department values such as "
        "'Engineering'. Verify the page displays the text 'Page 1 of 3'. Verify that "
        "clickable column headers for 'name', 'department', and 'salary' are present."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_browser_grid_renders",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
