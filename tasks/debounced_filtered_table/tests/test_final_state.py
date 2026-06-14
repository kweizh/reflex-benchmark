import os
import socket
import sqlite3
import subprocess
import time
from urllib.parse import urlencode

import pytest
import requests
from xprocess import ProcessStarter


PROJECT_DIR = "/home/user/filtered_table"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"

CATEGORIES = ["Electronics", "Books", "Clothing", "Home", "Toys", "Sports"]


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _wait_for_http(url: str, timeout: float = 180.0) -> bool:
    """Poll an HTTP endpoint until it responds with any HTTP status code."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code < 600:
                return True
        except requests.RequestException:
            pass
        time.sleep(2.0)
    return False


@pytest.fixture(scope="session")
def reflex_server(xprocess):
    """Start the reflex server fresh and wait for both ports to be ready."""

    class Starter(ProcessStarter):
        name = "reflex_filtered_table"
        args = [
            "uv",
            "run",
            "reflex",
            "run",
            "--backend-port",
            str(BACKEND_PORT),
            "--frontend-port",
            str(FRONTEND_PORT),
            "--loglevel",
            "info",
        ]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            return _port_open("localhost", BACKEND_PORT) and _port_open(
                "localhost", FRONTEND_PORT
            )

    xprocess.ensure(Starter.name, Starter)

    # Give frontend a moment to finish first compile after socket is open.
    assert _wait_for_http(f"{BACKEND_URL}/api/filter", timeout=120), (
        "Backend /api/filter endpoint did not become reachable in time."
    )
    assert _wait_for_http(f"{FRONTEND_URL}/", timeout=180), (
        "Frontend / page did not become reachable in time."
    )

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()


# ---------------------------------------------------------------------------
# Source-code checks (no server needed)
# ---------------------------------------------------------------------------


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Reflex project directory missing at {PROJECT_DIR}."
    )


def test_rxconfig_present():
    rxconfig = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig), (
        f"rxconfig.py not found at {rxconfig}; reflex project may not be initialized."
    )


def test_reflex_db_file_exists():
    assert os.path.isfile(DB_PATH), (
        f"SQLite database not found at {DB_PATH}; the executor must seed it during setup."
    )


@pytest.mark.parametrize(
    "needle",
    [
        "rx.debounce_input",
        "debounce_timeout=300",
        "rx.asession",
        "rx.foreach",
        "background=True",
        "api_transformer",
    ],
)
def test_source_contains_required_idiom(needle: str):
    """grep the project source tree for required Reflex idioms."""
    result = subprocess.run(
        [
            "grep",
            "-R",
            "-F",
            "--include=*.py",
            needle,
            PROJECT_DIR,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and result.stdout.strip(), (
        f"Expected the literal idiom {needle!r} to appear in the project source under "
        f"{PROJECT_DIR}. grep stdout was: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Seed database checks (raw sqlite3, no reflex import needed)
# ---------------------------------------------------------------------------


def _query(sql: str, params: tuple = ()):  # noqa: ANN201 - internal helper
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def test_seed_total_row_count():
    rows = _query("SELECT COUNT(*) FROM product")
    assert rows[0][0] == 240, (
        f"Expected exactly 240 rows in the product table, found {rows[0][0]}."
    )


def test_seed_per_category_counts():
    rows = _query(
        "SELECT category, COUNT(*) FROM product GROUP BY category ORDER BY category"
    )
    actual = dict(rows)
    expected = {c: 40 for c in CATEGORIES}
    assert actual == expected, (
        f"Expected 40 rows per category {sorted(CATEGORIES)}, got {actual}."
    )


def test_seed_in_stock_count():
    rows = _query("SELECT COUNT(*) FROM product WHERE in_stock = 1")
    assert rows[0][0] == 180, (
        f"Expected 180 in-stock rows (30 per category x 6), got {rows[0][0]}."
    )


def test_seed_first_row():
    rows = _query(
        "SELECT name, sku, price, in_stock FROM product WHERE id = 1"
    )
    assert rows, "No row with id=1; insertion order may be wrong."
    name, sku, price, in_stock = rows[0]
    assert name == "Electronics #01", (
        f"id=1 should be 'Electronics #01', got {name!r}."
    )
    assert sku == "ELE-001", f"id=1 sku should be 'ELE-001', got {sku!r}."
    assert float(price) == pytest.approx(5.0), (
        f"id=1 price should be 5.0, got {price!r}."
    )
    assert int(in_stock) == 1, (
        f"id=1 should be in stock (i=0, 0%4=0), got in_stock={in_stock!r}."
    )


def test_seed_last_row():
    rows = _query(
        "SELECT name, sku, price, in_stock FROM product WHERE id = 240"
    )
    assert rows, "No row with id=240; insertion order may be wrong."
    name, sku, price, in_stock = rows[0]
    assert name == "Sports #40", (
        f"id=240 should be 'Sports #40', got {name!r}."
    )
    assert sku == "SPO-040", f"id=240 sku should be 'SPO-040', got {sku!r}."
    assert float(price) == pytest.approx(69.0), (
        f"id=240 price should be 69.0, got {price!r}."
    )
    assert int(in_stock) == 0, (
        f"id=240 should NOT be in stock (i=39, 39%4=3), got in_stock={in_stock!r}."
    )


def test_seed_books_second_row():
    rows = _query("SELECT name, price FROM product WHERE id = 42")
    assert rows, "No row with id=42; insertion order may be wrong."
    name, price = rows[0]
    assert name == "Books #02", f"id=42 should be 'Books #02', got {name!r}."
    assert float(price) == pytest.approx(11.0), (
        f"id=42 price should be 11.0, got {price!r}."
    )


# ---------------------------------------------------------------------------
# Live server checks (requires running reflex)
# ---------------------------------------------------------------------------


def test_frontend_page_renders(reflex_server):
    response = requests.get(f"{FRONTEND_URL}/", timeout=30)
    assert response.status_code == 200, (
        f"Expected HTTP 200 from {FRONTEND_URL}/, got {response.status_code}."
    )
    assert response.text.strip(), (
        f"Frontend body at {FRONTEND_URL}/ is empty; page did not render."
    )


def _filter(params: dict) -> dict:
    qs = urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BACKEND_URL}/api/filter"
    if qs:
        url = f"{url}?{qs}"
    response = requests.get(url, timeout=30)
    assert response.status_code == 200, (
        f"GET {url} expected status 200, got {response.status_code}; body={response.text[:500]!r}"
    )
    data = response.json()
    assert "result_count" in data and "filtered" in data, (
        f"GET {url} JSON missing required keys; got keys={list(data.keys())}."
    )
    assert isinstance(data["filtered"], list), (
        f"GET {url} 'filtered' field must be a list, got {type(data['filtered'])}."
    )
    assert len(data["filtered"]) == data["result_count"], (
        f"GET {url} result_count={data['result_count']} but len(filtered)="
        f"{len(data['filtered'])}; these MUST match."
    )
    return data


def test_filter_no_filters_default_sort(reflex_server):
    data = _filter({"sort_by": "id", "sort_dir": "asc"})
    assert data["result_count"] == 240, (
        f"Unfiltered query should return all 240 rows, got {data['result_count']}."
    )
    first = data["filtered"][0]
    last = data["filtered"][-1]
    assert first["id"] == 1 and first["name"] == "Electronics #01", (
        f"First row of asc-by-id should be id=1 'Electronics #01', got {first}."
    )
    assert last["id"] == 240 and last["name"] == "Sports #40", (
        f"Last row of asc-by-id should be id=240 'Sports #40', got {last}."
    )


def test_filter_category_books(reflex_server):
    data = _filter({"category": "Books"})
    assert data["result_count"] == 40, (
        f"category=Books should return 40 rows, got {data['result_count']}."
    )
    for row in data["filtered"]:
        assert row["category"] == "Books", (
            f"category=Books returned a row with category={row['category']!r}."
        )


def test_filter_books_in_stock_only(reflex_server):
    data = _filter({"category": "Books", "in_stock_only": "true"})
    assert data["result_count"] == 30, (
        f"category=Books & in_stock_only should return 30 rows, got {data['result_count']}."
    )
    for row in data["filtered"]:
        assert row["category"] == "Books", row
        assert row["in_stock"] is True or row["in_stock"] == 1, (
            f"in_stock_only=true should not return out-of-stock rows; got {row}."
        )


def test_filter_price_window_20_to_30(reflex_server):
    data = _filter({"min_price": 20, "max_price": 30})
    assert data["result_count"] == 51, (
        f"min_price=20 & max_price=30 should return 51 rows, got {data['result_count']}."
    )
    for row in data["filtered"]:
        assert 20.0 <= float(row["price"]) <= 30.0, (
            f"Price-window filter returned out-of-range row: {row}."
        )


def test_filter_text_search_books_hash_one(reflex_server):
    data = _filter({"search": "Books #1"})
    assert data["result_count"] == 10, (
        f"search='Books #1' should return 10 rows (Books #10 - Books #19), "
        f"got {data['result_count']}."
    )
    for row in data["filtered"]:
        assert "Books #1" in row["name"], (
            f"search='Books #1' returned a non-matching row: {row}."
        )


def test_filter_sort_price_desc(reflex_server):
    data = _filter({"sort_by": "price", "sort_dir": "desc"})
    assert data["result_count"] == 240, (
        f"Unfiltered sort-by-price-desc should return 240 rows, got {data['result_count']}."
    )
    top = data["filtered"][0]
    bottom = data["filtered"][-1]
    assert top["name"] == "Sports #40" and float(top["price"]) == pytest.approx(69.0), (
        f"Top of price-desc should be Sports #40 @ 69.0, got {top}."
    )
    assert bottom["name"] == "Electronics #01" and float(bottom["price"]) == pytest.approx(
        5.0
    ), (
        f"Bottom of price-desc should be Electronics #01 @ 5.0, got {bottom}."
    )


def test_filter_in_stock_only_sort_name_asc(reflex_server):
    data = _filter({"in_stock_only": "true", "sort_by": "name", "sort_dir": "asc"})
    assert data["result_count"] == 180, (
        f"in_stock_only should return 180 rows, got {data['result_count']}."
    )
    first = data["filtered"][0]
    assert first["name"] == "Books #01", (
        f"Lexicographically smallest in-stock name should be 'Books #01', got {first}."
    )


def test_filter_combined_electronics_under_20_in_stock(reflex_server):
    data = _filter(
        {
            "category": "Electronics",
            "max_price": 20,
            "in_stock_only": "true",
            "sort_by": "price",
            "sort_dir": "asc",
        }
    )
    assert data["result_count"] == 12, (
        f"Electronics & price<=20 & in_stock_only should return 12 rows, "
        f"got {data['result_count']}."
    )
    first = data["filtered"][0]
    assert first["name"] == "Electronics #01" and float(first["price"]) == pytest.approx(
        5.0
    ), (
        f"First row of combined filter should be Electronics #01 @ 5.0, got {first}."
    )
    for row in data["filtered"]:
        assert row["category"] == "Electronics", row
        assert float(row["price"]) <= 20.0, row
        assert row["in_stock"] is True or row["in_stock"] == 1, row
