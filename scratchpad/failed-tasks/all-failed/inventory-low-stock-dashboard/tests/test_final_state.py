import os
import shutil
import socket
import sqlite3
import subprocess

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/inventory_app"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")

# Bind/connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback
# (::1) while the servers listen on the IPv4 loopback only, which would make the
# readiness check hang for the full timeout.
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"


def _free_ports():
    """Best-effort: free ports 3000/8000 in case a stale server is still running."""
    fuser = shutil.which("fuser")
    if fuser is not None:
        subprocess.run(
            [fuser, "-k", f"{FRONTEND_PORT}/tcp", f"{BACKEND_PORT}/tcp"],
            capture_output=True,
            text=True,
        )
    pkill = shutil.which("pkill")
    if pkill is not None:
        subprocess.run([pkill, "-f", "reflex run"], capture_output=True, text=True)


def _reset_database():
    """Reset to a deterministic, freshly seeded state.

    Remove the SQLite file and re-apply migrations so that, when the app starts,
    it seeds the initial products into an empty table.
    """
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    result = subprocess.run(
        ["uv", "run", "reflex", "db", "migrate"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    print("=== reflex db migrate stdout ===")
    print(result.stdout)
    print("=== reflex db migrate stderr ===")
    print(result.stderr)
    assert result.returncode == 0, (
        f"'uv run reflex db migrate' failed with code {result.returncode}: {result.stderr}"
    )


@pytest.fixture(scope="session")
def start_app(xprocess):
    _free_ports()
    _reset_database()

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        # CRITICAL: set `env` as a class attribute, NEVER inside popen_kwargs.
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First run compiles the Next.js frontend which can take a while.
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            # Both ports must accept connections first.
            for port in (BACKEND_PORT, FRONTEND_PORT):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex((HOST, port)) != 0:
                        return False
            # Backend health endpoint should answer "pong".
            try:
                ping = requests.get(f"{BACKEND_URL}/ping/", timeout=20)
                if ping.status_code != 200:
                    return False
            except requests.RequestException:
                return False
            # Frontend should serve a page (first request triggers bundling).
            try:
                front = requests.get(FRONTEND_URL, timeout=30)
                return front.status_code < 500
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
        printed_log_lines = len(all_lines)
        print(f"===== [{tag}] {Starter.name} log begin =====")
        print("".join(new_lines))
        print(f"===== [{tag}] {Starter.name} log end =====")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()
    _free_ports()


def test_backend_ping(start_app):
    resp = requests.get(f"{BACKEND_URL}/ping/", timeout=20)
    assert resp.status_code == 200, (
        f"Backend /ping/ returned status {resp.status_code}, expected 200."
    )
    assert "pong" in resp.text.lower(), (
        f"Backend /ping/ body should contain 'pong', got: {resp.text!r}"
    )


def test_frontend_renders_dashboard(start_app):
    resp = requests.get(FRONTEND_URL, timeout=30)
    assert resp.status_code == 200, (
        f"Frontend returned status {resp.status_code}, expected 200."
    )
    assert "inventory dashboard" in resp.text.lower(), (
        "Frontend HTML should contain the heading text 'Inventory Dashboard'."
    )


def test_seed_persisted_in_sqlite(start_app):
    assert os.path.isfile(DB_PATH), f"SQLite database not found at {DB_PATH}."
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT sku, quantity, price, reorder_threshold FROM product ORDER BY sku"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 5, (
        f"Expected exactly 5 seeded products in the 'product' table, found {len(rows)}."
    )

    by_sku = {r["sku"]: r for r in rows}
    expected = {
        "BOLT-M6": (8, 0.25, 20),
        "HINGE-ST": (50, 3.50, 15),
        "WIRE-CU10": (5, 12.00, 10),
        "GROM-PL": (200, 0.10, 100),
        "GASK-RB": (12, 1.75, 12),
    }
    for sku, (qty, price, threshold) in expected.items():
        assert sku in by_sku, f"Seed product with sku '{sku}' missing from database."
        row = by_sku[sku]
        assert row["quantity"] == qty, (
            f"Product {sku}: expected quantity {qty}, got {row['quantity']}."
        )
        assert abs(row["price"] - price) < 1e-6, (
            f"Product {sku}: expected price {price}, got {row['price']}."
        )
        assert row["reorder_threshold"] == threshold, (
            f"Product {sku}: expected reorder_threshold {threshold}, got {row['reorder_threshold']}."
        )


def test_products_api_initial(start_app):
    resp = requests.get(f"{BACKEND_URL}/api/products", timeout=20)
    assert resp.status_code == 200, (
        f"GET /api/products returned {resp.status_code}, expected 200."
    )
    products = resp.json()
    assert isinstance(products, list) and len(products) == 5, (
        f"GET /api/products should return a list of 5 products, got: {products}"
    )
    skus = [p["sku"] for p in products]
    assert skus == sorted(skus), (
        f"Products must be ordered by sku ascending, got order: {skus}"
    )
    assert products[0]["sku"] == "BOLT-M6", (
        f"First product (sku ascending) should be BOLT-M6, got {products[0]['sku']}."
    )
    expected_keys = {"name", "sku", "quantity", "price", "reorder_threshold"}
    for p in products:
        assert set(p.keys()) == expected_keys, (
            f"Each product object must have exactly the keys {sorted(expected_keys)}, "
            f"got {sorted(p.keys())}."
        )


def _get_stats():
    resp = requests.get(f"{BACKEND_URL}/api/stats", timeout=20)
    assert resp.status_code == 200, (
        f"GET /api/stats returned {resp.status_code}, expected 200."
    )
    return resp.json()


def test_stats_and_adjustments(start_app):
    # --- Initial aggregate stats ---
    stats = _get_stats()
    assert abs(stats["total_inventory_value"] - 278.0) < 1e-6, (
        f"Initial total_inventory_value should be 278.0, got {stats['total_inventory_value']}."
    )
    assert stats["low_stock_count"] == 2, (
        f"Initial low_stock_count should be 2, got {stats['low_stock_count']}."
    )
    low_skus = sorted(p["sku"] for p in stats["low_stock_products"])
    assert low_skus == ["BOLT-M6", "WIRE-CU10"], (
        f"Initial low_stock_products should be BOLT-M6 and WIRE-CU10, got {low_skus}."
    )

    # --- Adjust WIRE-CU10 up by 20 (5 -> 25), clearing its low-stock status ---
    resp = requests.post(
        f"{BACKEND_URL}/api/adjust",
        json={"sku": "WIRE-CU10", "delta": 20},
        timeout=20,
    )
    assert resp.status_code == 200, (
        f"POST /api/adjust (WIRE-CU10 +20) returned {resp.status_code}, expected 200."
    )
    assert resp.json()["quantity"] == 25, (
        f"After +20, WIRE-CU10 quantity should be 25, got {resp.json()['quantity']}."
    )

    stats = _get_stats()
    assert abs(stats["total_inventory_value"] - 518.0) < 1e-6, (
        f"After WIRE-CU10 +20, total_inventory_value should be 518.0, got {stats['total_inventory_value']}."
    )
    assert stats["low_stock_count"] == 1, (
        f"After WIRE-CU10 +20, low_stock_count should be 1, got {stats['low_stock_count']}."
    )
    low_skus = sorted(p["sku"] for p in stats["low_stock_products"])
    assert low_skus == ["BOLT-M6"], (
        f"After WIRE-CU10 +20, low_stock_products should be only BOLT-M6, got {low_skus}."
    )

    # --- Adjust BOLT-M6 down by 100; must clamp at 0 (not negative) ---
    resp = requests.post(
        f"{BACKEND_URL}/api/adjust",
        json={"sku": "BOLT-M6", "delta": -100},
        timeout=20,
    )
    assert resp.status_code == 200, (
        f"POST /api/adjust (BOLT-M6 -100) returned {resp.status_code}, expected 200."
    )
    assert resp.json()["quantity"] == 0, (
        f"After -100, BOLT-M6 quantity should clamp to 0, got {resp.json()['quantity']}."
    )

    # Verify the clamped value was persisted to SQLite.
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT quantity FROM product WHERE sku = ?", ("BOLT-M6",)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] == 0, (
        f"Persisted BOLT-M6 quantity should be 0 after clamp, got {row}."
    )

    stats = _get_stats()
    assert abs(stats["total_inventory_value"] - 516.0) < 1e-6, (
        f"After BOLT-M6 clamp, total_inventory_value should be 516.0, got {stats['total_inventory_value']}."
    )
    assert stats["low_stock_count"] == 1, (
        f"After BOLT-M6 clamp to 0, low_stock_count should still be 1, got {stats['low_stock_count']}."
    )

    # --- Unknown SKU must 404 ---
    resp = requests.post(
        f"{BACKEND_URL}/api/adjust",
        json={"sku": "DOES-NOT-EXIST", "delta": 5},
        timeout=20,
    )
    assert resp.status_code == 404, (
        f"POST /api/adjust with unknown sku should return 404, got {resp.status_code}."
    )
