import json
import os
import socket
import subprocess

import pytest
import requests
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/checkout_app"
DRIVER_PATH = os.path.join(PROJECT_DIR, "_verify_driver.py")

HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


# ---------------------------------------------------------------------------
# In-process driver: exercises the chained checkout pipeline deterministically
# by importing CheckoutState / Product / Order from the app and driving the
# event chain generically (following yielded/returned event handlers).
# Executed inside the project's uv environment because Reflex is not importable
# from the system python3.
# ---------------------------------------------------------------------------
DRIVER_CODE = r'''
import sys
import json
import inspect
import asyncio

import reflex as rx
from checkout_app.checkout_app import CheckoutState, Product, Order


def ensure_tables():
    try:
        from reflex.model import get_engine
        rx.Model.metadata.create_all(get_engine())
    except Exception as e:  # pragma: no cover - best effort
        print("ensure_tables warning:", e, file=sys.stderr)


def seed(products):
    with rx.session() as s:
        for o in s.exec(Order.select()).all():
            s.delete(o)
        for p in s.exec(Product.select()).all():
            s.delete(p)
        s.commit()
    with rx.session() as s:
        for name, stock, price in products:
            s.add(Product(name=name, stock=stock, price=price))
        s.commit()


def handler_name(item):
    fn = getattr(item, "fn", None)
    if fn is not None and hasattr(fn, "__name__"):
        return fn.__name__
    h = getattr(item, "handler", None)
    if h is not None:
        fn2 = getattr(h, "fn", None)
        if fn2 is not None and hasattr(fn2, "__name__"):
            return fn2.__name__
    return None


async def run_result(state, result, statuses):
    if result is None:
        return
    if inspect.isasyncgen(result):
        async for item in result:
            await on_yield(state, item, statuses)
    elif inspect.isgenerator(result):
        for item in result:
            await on_yield(state, item, statuses)
    elif inspect.iscoroutine(result):
        ret = await result
        await on_event(state, ret, statuses)
    else:
        await on_event(state, result, statuses)


async def on_yield(state, item, statuses):
    statuses.append(str(state.status_message))
    await on_event(state, item, statuses)


async def on_event(state, item, statuses):
    if item is None:
        return
    if isinstance(item, (list, tuple)):
        for sub in item:
            await on_event(state, sub, statuses)
        return
    name = handler_name(item)
    if name:
        nxt = getattr(state, name)()
        await run_result(state, nxt, statuses)


async def drive(state):
    statuses = []
    result = getattr(state, "place_order")()
    await run_result(state, result, statuses)
    statuses.append(str(state.status_message))
    return statuses


def read_products(names):
    out = {}
    with rx.session() as s:
        for n in names:
            p = s.exec(Product.select().where(Product.name == n)).first()
            out[n] = (None if p is None else int(p.stock))
    return out


def read_orders():
    out = []
    with rx.session() as s:
        for r in s.exec(Order.select()).all():
            out.append(
                {
                    "product_name": r.product_name,
                    "quantity": int(r.quantity),
                    "status": r.status,
                }
            )
    return out


async def main():
    ensure_tables()
    out = {}

    # Scenario 1: success path.
    seed([("widget", 5, 2.0), ("gadget", 10, 3.0)])
    s1 = CheckoutState(_reflex_internal_init=True)
    s1.cart = {"widget": 2}
    statuses1 = await drive(s1)
    out["s1"] = {
        "statuses": statuses1,
        "final_status": str(s1.status_message),
        "current_step": str(s1.current_step),
        "products": read_products(["widget", "gadget"]),
        "orders": read_orders(),
    }

    # Scenario 2: transactional rollback on insufficient stock.
    seed([("widget", 5, 2.0), ("gadget", 3, 3.0)])
    s2 = CheckoutState(_reflex_internal_init=True)
    s2.cart = {"widget": 1, "gadget": 100}
    statuses2 = await drive(s2)
    out["s2"] = {
        "statuses": statuses2,
        "final_status": str(s2.status_message),
        "current_step": str(s2.current_step),
        "products": read_products(["widget", "gadget"]),
        "orders": read_orders(),
    }

    # Scenario 3: idle computed var default.
    s3 = CheckoutState(_reflex_internal_init=True)
    out["s3"] = {"current_step": str(s3.current_step)}

    print("RESULT_JSON:" + json.dumps(out))


asyncio.run(main())
'''


@pytest.fixture(scope="session")
def driver_results():
    with open(DRIVER_PATH, "w") as f:
        f.write(DRIVER_CODE)

    env = os.environ.copy()
    env["REFLEX_TELEMETRY_ENABLED"] = "false"

    result = subprocess.run(
        ["uv", "run", "python", DRIVER_PATH],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    print("===== driver stdout =====")
    print(result.stdout)
    print("===== driver stderr =====")
    print(result.stderr)

    assert result.returncode == 0, (
        "The checkout pipeline driver failed to run inside the project env. "
        f"returncode={result.returncode}"
    )

    payload = None
    for line in result.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            payload = json.loads(line[len("RESULT_JSON:"):])
    assert payload is not None, "Driver did not emit a RESULT_JSON line with results."
    return payload


def _first_index(statuses, needle):
    low = needle.lower()
    for i, s in enumerate(statuses):
        if low in str(s).lower():
            return i
    return -1


def test_success_chaining_and_status_sequence(driver_results):
    s1 = driver_results["s1"]
    statuses = s1["statuses"]
    idx_validate = _first_index(statuses, "Validating")
    idx_reserve = _first_index(statuses, "Reserving")
    idx_confirm = _first_index(statuses, "Confirmed")
    assert idx_validate >= 0, f"No 'Validating' status was yielded. Got: {statuses}"
    assert idx_reserve >= 0, f"No 'Reserving' status was yielded. Got: {statuses}"
    assert idx_confirm >= 0, f"No 'Confirmed' status was yielded. Got: {statuses}"
    assert idx_validate < idx_reserve < idx_confirm, (
        "Chained stages must yield status updates in order "
        f"Validating -> Reserving -> Confirmed. Got: {statuses}"
    )


def test_success_final_state(driver_results):
    s1 = driver_results["s1"]
    assert "confirmed" in s1["final_status"].lower(), (
        f"Final status after a successful order should mention 'Confirmed'. Got: {s1['final_status']!r}"
    )
    assert s1["current_step"] == "Confirmed", (
        f"Computed var current_step should be 'Confirmed' after success. Got: {s1['current_step']!r}"
    )


def test_success_stock_deducted(driver_results):
    s1 = driver_results["s1"]
    assert s1["products"]["widget"] == 3, (
        f"widget stock should be 5-2=3 after a successful reservation. Got: {s1['products']}"
    )


def test_success_order_created(driver_results):
    s1 = driver_results["s1"]
    widget_orders = [
        o
        for o in s1["orders"]
        if o["product_name"] == "widget" and o["status"] == "confirmed"
    ]
    assert len(widget_orders) >= 1, (
        f"Expected a confirmed Order row for 'widget'. Got orders: {s1['orders']}"
    )
    assert any(o["quantity"] == 2 for o in widget_orders), (
        f"Expected a confirmed 'widget' Order with quantity 2. Got: {widget_orders}"
    )


def test_rollback_status_and_step(driver_results):
    s2 = driver_results["s2"]
    assert _first_index(s2["statuses"], "Validating") >= 0, (
        f"Failure path should still yield a 'Validating' status. Got: {s2['statuses']}"
    )
    assert "insufficient stock" in s2["final_status"].lower(), (
        f"Final status on insufficient stock should mention 'Insufficient stock'. Got: {s2['final_status']!r}"
    )
    assert s2["current_step"] == "Failed", (
        f"Computed var current_step should be 'Failed' after a failed checkout. Got: {s2['current_step']!r}"
    )


def test_rollback_no_partial_deduction(driver_results):
    s2 = driver_results["s2"]
    assert s2["products"]["widget"] == 5, (
        "On a failed all-or-nothing reservation, widget stock must remain 5 (no partial deduction). "
        f"Got: {s2['products']}"
    )
    assert s2["products"]["gadget"] == 3, (
        "On a failed all-or-nothing reservation, gadget stock must remain 3. "
        f"Got: {s2['products']}"
    )


def test_rollback_no_orders(driver_results):
    s2 = driver_results["s2"]
    assert len(s2["orders"]) == 0, (
        f"No Order rows should be created when the reservation fails. Got: {s2['orders']}"
    )


def test_idle_computed_var(driver_results):
    s3 = driver_results["s3"]
    assert s3["current_step"] == "Idle", (
        f"Computed var current_step should default to 'Idle' before any checkout. Got: {s3['current_step']!r}"
    )


# ---------------------------------------------------------------------------
# Server smoke test: the app must actually run and serve the UI on port 3000.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def start_app(xprocess):
    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        env = {**os.environ, "REFLEX_TELEMETRY_ENABLED": "false"}
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 420
        terminate_on_interrupt = True

        def startup_check(self):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
            try:
                resp = requests.get(BASE_URL, timeout=30)
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
            lines = []
        new = lines[printed:]
        printed = len(lines)
        print(f"===== [{tag}] reflex_app log =====")
        print("".join(new))
        print(f"===== [{tag}] end reflex_app log =====")

    started = False
    try:
        xprocess.ensure(Starter.name, Starter)
        started = True
    finally:
        capture_logs("STARTED" if started else "FAILED")

    yield

    capture_logs("TEARDOWN")
    info.terminate()


def test_frontend_serves_checkout_page(start_app):
    resp = requests.get(BASE_URL, timeout=30)
    assert resp.status_code == 200, (
        f"GET {BASE_URL} should return 200. Got: {resp.status_code}"
    )
    assert "checkout" in resp.text.lower(), (
        "The served page should contain the heading text 'Checkout'."
    )


def test_backend_port_listening(start_app):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex((HOST, BACKEND_PORT))
    assert result == 0, (
        f"The Reflex backend should be listening on port {BACKEND_PORT} while the app runs."
    )
