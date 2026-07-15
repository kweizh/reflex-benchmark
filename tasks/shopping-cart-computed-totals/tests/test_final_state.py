import importlib.util
import os
import socket

import pytest
import requests
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/shopping_cart"
CART_CORE_PATH = os.path.join(PROJECT_DIR, "shopping_cart", "cart_core.py")

FRONTEND_PORT = 3000
BACKEND_PORT = 8000
# Connect over IPv4 explicitly. `localhost` can resolve to the IPv6 loopback (::1)
# while the dev server listens on 127.0.0.1 only, which would make the readiness
# check hang for the whole timeout.
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{FRONTEND_PORT}"


# ---------------------------------------------------------------------------
# Section A: pure pricing logic (no Reflex import required)
# ---------------------------------------------------------------------------


def _load_cart_core():
    assert os.path.isfile(CART_CORE_PATH), f"Pricing module not found at {CART_CORE_PATH}."
    spec = importlib.util.spec_from_file_location("cart_core", CART_CORE_PATH)
    assert spec is not None and spec.loader is not None, (
        f"Unable to build an import spec for {CART_CORE_PATH}."
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE_ITEMS = [
    {"name": "Coffee Mug", "price": 12.5, "quantity": 2},
    {"name": "Notebook", "price": 8.0, "quantity": 1},
]


def test_cart_core_importable_without_reflex():
    module = _load_cart_core()
    assert hasattr(module, "compute_totals"), "cart_core must expose a compute_totals function."


def test_tax_rate_constant():
    module = _load_cart_core()
    assert hasattr(module, "TAX_RATE"), "cart_core must define TAX_RATE."
    assert module.TAX_RATE == pytest.approx(0.08), f"Expected TAX_RATE == 0.08, got {module.TAX_RATE}."


def test_discount_codes_defined():
    module = _load_cart_core()
    assert hasattr(module, "DISCOUNT_CODES"), "cart_core must define DISCOUNT_CODES."
    codes = module.DISCOUNT_CODES
    assert codes.get("SAVE10") == pytest.approx(0.10), f"SAVE10 must map to 0.10, got {codes.get('SAVE10')}."
    assert codes.get("SAVE20") == pytest.approx(0.20), f"SAVE20 must map to 0.20, got {codes.get('SAVE20')}."
    assert codes.get("WELCOME5") == pytest.approx(0.05), (
        f"WELCOME5 must map to 0.05, got {codes.get('WELCOME5')}."
    )


def test_empty_cart_totals_are_zero():
    module = _load_cart_core()
    result = module.compute_totals([], "")
    assert set(result.keys()) == {"subtotal", "discount", "tax", "total"}, (
        f"compute_totals must return exactly the keys subtotal, discount, tax, total; got {set(result.keys())}."
    )
    for key in ("subtotal", "discount", "tax", "total"):
        assert result[key] == pytest.approx(0.0), f"Empty cart {key} should be 0, got {result[key]}."


def test_totals_without_code():
    module = _load_cart_core()
    result = module.compute_totals(SAMPLE_ITEMS, "")
    assert result["subtotal"] == pytest.approx(33.0, abs=0.01), f"subtotal should be 33.0, got {result['subtotal']}."
    assert result["discount"] == pytest.approx(0.0, abs=0.01), f"discount should be 0.0, got {result['discount']}."
    assert result["tax"] == pytest.approx(2.64, abs=0.01), f"tax should be 2.64, got {result['tax']}."
    assert result["total"] == pytest.approx(35.64, abs=0.01), f"total should be 35.64, got {result['total']}."


def test_totals_with_valid_code():
    module = _load_cart_core()
    result = module.compute_totals(SAMPLE_ITEMS, "SAVE10")
    assert result["subtotal"] == pytest.approx(33.0, abs=0.01), f"subtotal should be 33.0, got {result['subtotal']}."
    assert result["discount"] == pytest.approx(3.3, abs=0.01), f"discount should be 3.3, got {result['discount']}."
    assert result["tax"] == pytest.approx(2.38, abs=0.01), f"tax should be 2.38, got {result['tax']}."
    assert result["total"] == pytest.approx(32.08, abs=0.01), f"total should be 32.08, got {result['total']}."


def test_code_is_case_insensitive():
    module = _load_cart_core()
    lower = module.compute_totals(SAMPLE_ITEMS, "save10")
    upper = module.compute_totals(SAMPLE_ITEMS, "SAVE10")
    assert lower["discount"] == pytest.approx(upper["discount"], abs=0.01), (
        f"Lower-case 'save10' should match 'SAVE10'; got discounts {lower['discount']} vs {upper['discount']}."
    )
    assert lower["total"] == pytest.approx(upper["total"], abs=0.01), (
        f"Lower-case 'save10' should match 'SAVE10'; got totals {lower['total']} vs {upper['total']}."
    )


def test_invalid_code_applies_no_discount():
    module = _load_cart_core()
    result = module.compute_totals(SAMPLE_ITEMS, "BOGUS")
    assert result["discount"] == pytest.approx(0.0, abs=0.01), (
        f"Invalid code should produce no discount, got {result['discount']}."
    )
    assert result["tax"] == pytest.approx(2.64, abs=0.01), f"tax should be 2.64, got {result['tax']}."
    assert result["total"] == pytest.approx(35.64, abs=0.01), f"total should be 35.64, got {result['total']}."


def test_totals_with_save20():
    module = _load_cart_core()
    result = module.compute_totals(SAMPLE_ITEMS, "SAVE20")
    assert result["discount"] == pytest.approx(6.6, abs=0.01), f"discount should be 6.6, got {result['discount']}."
    assert result["tax"] == pytest.approx(2.11, abs=0.01), f"tax should be 2.11, got {result['tax']}."
    assert result["total"] == pytest.approx(28.51, abs=0.01), f"total should be 28.51, got {result['total']}."


# ---------------------------------------------------------------------------
# Section B: running app + browser behavior
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server with uv and wait until the frontend responds."""

    class Starter(ProcessStarter):
        name = "shopping_cart_app"
        args = [
            "uv",
            "run",
            "reflex",
            "run",
            "--frontend-port",
            str(FRONTEND_PORT),
            "--backend-port",
            str(BACKEND_PORT),
        ]
        # CRITICAL: set `env` as a class attribute here, NEVER inside `popen_kwargs`.
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        # First compile of the Next.js frontend can be slow.
        timeout = 300
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


def test_backend_port_open(start_app):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        result = s.connect_ex((HOST, BACKEND_PORT))
    assert result == 0, f"Reflex backend is not accepting connections on {HOST}:{BACKEND_PORT}."


def test_frontend_serves_page(start_app):
    resp = requests.get(BASE_URL, timeout=30)
    assert resp.status_code == 200, f"GET {BASE_URL} returned status {resp.status_code}."


def test_shopping_cart_behavior(start_app, browser_verifier):
    reason = (
        "The homepage should be an interactive shopping cart. Users pick products from a fixed "
        "catalog, adjust quantities, apply discount codes, and see live subtotal/discount/tax/total "
        "figures. The cart persists in browser local storage and is restored after a page reload. "
        "An empty cart shows an empty-cart message."
    )
    truth = (
        f"Navigate to {BASE_URL}. "
        "Verify the page shows the heading text 'Shopping Cart' and, while the cart is empty, the text "
        "'Your cart is empty'. "
        "Add one product from the catalog to the cart. Verify the 'Your cart is empty' message disappears, "
        "a cart line for that product appears, and the subtotal and grand total become non-zero values that "
        "reflect the product's price. "
        "Increase that product's quantity by one and verify the subtotal and grand total increase accordingly. "
        "Type the discount code 'SAVE10' into the discount code input and apply it; verify a non-zero discount "
        "amount is shown and the grand total is reduced compared to before the code was applied. "
        "Clear the code input, type an invalid code 'BOGUS', and apply it; verify an error message indicating "
        "the code is invalid appears and no discount is applied. "
        "Reload the page and verify the product previously added is still present in the cart (it was persisted "
        "to local storage and restored on load). "
        "Remove the product from the cart and verify the cart becomes empty again with the 'Your cart is empty' "
        "message shown."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_shopping_cart_behavior",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
