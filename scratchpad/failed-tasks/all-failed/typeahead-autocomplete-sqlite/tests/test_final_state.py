import csv
import os
import socket
import subprocess

import pytest
import requests
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier

PROJECT_DIR = "/home/user/catalog_app"
SEED_CSV = os.path.join(PROJECT_DIR, "products.csv")

HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"

RESULT_KEYS = {"id", "name", "category", "price", "description"}


# --------------------------------------------------------------------------
# Reference implementation of the ranking / label logic (mirrors task spec).
# Expectations are derived from the same seed CSV the app loads, so there are
# no magic numbers.
# --------------------------------------------------------------------------
def load_products():
    with open(SEED_CSV, newline="") as f:
        reader = csv.DictReader(f)
        products = []
        for row in reader:
            products.append(
                {
                    "name": row["name"],
                    "category": row["category"],
                    "price": float(row["price"]),
                    "description": row["description"],
                }
            )
    return products


def reference_rank(query, products):
    q = query.strip().lower()
    if not q:
        return []
    matches = [p for p in products if q in p["name"].lower()]

    def sort_key(p):
        name_l = p["name"].lower()
        group = 0 if name_l.startswith(q) else 1
        return (group, name_l)

    matches.sort(key=sort_key)
    return matches[:8]


def reference_label(query, results):
    if not query.strip():
        return "Start typing to search the catalog"
    if len(results) == 0:
        return "No matches found"
    return f"{len(results)} results"


def get_suggest(query):
    resp = requests.get(f"{BACKEND_URL}/api/suggest", params={"q": query}, timeout=30)
    assert resp.status_code == 200, (
        f"/api/suggest?q={query!r} returned status {resp.status_code}: {resp.text}"
    )
    return resp.json()


# --------------------------------------------------------------------------
# Server fixture: start the real Reflex app (frontend :3000 + backend :8000).
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def start_app(xprocess):
    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 300
        terminate_on_interrupt = True

        def startup_check(self):
            # Backend must answer the reserved health route with "pong".
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, BACKEND_PORT)) != 0:
                    return False
            try:
                ping = requests.get(f"{BACKEND_URL}/ping", timeout=20)
                if ping.status_code == 404:
                    ping = requests.get(f"{BACKEND_URL}/ping/", timeout=20)
                if "pong" not in ping.text.lower():
                    return False
            except requests.RequestException:
                return False
            # Frontend dev server must also be serving.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((HOST, FRONTEND_PORT)) != 0:
                    return False
            try:
                resp = requests.get(FRONTEND_URL, timeout=30)
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
        print(f"===== [{tag}] {Starter.name} log begin =====")
        print("".join(new))
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
    # Best-effort: make sure no leftover frontend/backend server keeps a port.
    for pattern in ("reflex run", "next", "granian", "uvicorn"):
        subprocess.run(["pkill", "-f", pattern], check=False)


# --------------------------------------------------------------------------
# Backend / API tests
# --------------------------------------------------------------------------
def test_backend_ping(start_app):
    resp = requests.get(f"{BACKEND_URL}/ping", timeout=20)
    if resp.status_code == 404:
        resp = requests.get(f"{BACKEND_URL}/ping/", timeout=20)
    assert resp.status_code == 200, f"/ping returned {resp.status_code}"
    assert "pong" in resp.text.lower(), f"/ping did not return pong, got: {resp.text!r}"


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query(start_app, query):
    data = get_suggest(query)
    assert data["query"] == "", f"Empty query should yield query '' but got {data['query']!r}"
    assert data["count"] == 0, f"Empty query count should be 0 but got {data['count']}"
    assert data["results"] == [], f"Empty query results should be [] but got {data['results']}"
    assert data["label"] == "Start typing to search the catalog", (
        f"Empty query label wrong: {data['label']!r}"
    )


def _check_results_fields(results, products_by_name):
    for r in results:
        assert set(r.keys()) == RESULT_KEYS, (
            f"Result object must have exactly keys {RESULT_KEYS} but had {set(r.keys())}"
        )
        expected = products_by_name[r["name"]]
        assert r["category"] == expected["category"], (
            f"category mismatch for {r['name']}: {r['category']!r} vs {expected['category']!r}"
        )
        assert abs(float(r["price"]) - expected["price"]) < 1e-6, (
            f"price mismatch for {r['name']}: {r['price']} vs {expected['price']}"
        )
        assert r["description"] == expected["description"], (
            f"description mismatch for {r['name']}"
        )


def test_ranked_results_app(start_app):
    products = load_products()
    products_by_name = {p["name"]: p for p in products}
    expected = reference_rank("app", products)
    expected_names = [p["name"] for p in expected]

    data = get_suggest("app")
    assert data["query"] == "app", f"query echoed wrong: {data['query']!r}"
    got_names = [r["name"] for r in data["results"]]
    assert got_names == expected_names, (
        f"Ranked names for 'app' wrong.\n expected {expected_names}\n got      {got_names}"
    )
    assert data["count"] == len(expected_names), (
        f"count for 'app' should be {len(expected_names)} but got {data['count']}"
    )
    assert data["label"] == f"{len(expected_names)} results", (
        f"label for 'app' wrong: {data['label']!r}"
    )
    _check_results_fields(data["results"], products_by_name)


def test_case_insensitive(start_app):
    lower = get_suggest("app")
    upper = get_suggest("APP")
    assert [r["name"] for r in upper["results"]] == [r["name"] for r in lower["results"]], (
        "Uppercase query 'APP' did not return the same ordered results as 'app'."
    )
    assert upper["count"] == lower["count"], "count differs between 'APP' and 'app'."
    assert upper["label"] == lower["label"], "label differs between 'APP' and 'app'."


def test_prefix_before_substring_pro(start_app):
    products = load_products()
    expected_names = [p["name"] for p in reference_rank("pro", products)]
    data = get_suggest("pro")
    got_names = [r["name"] for r in data["results"]]
    assert got_names == expected_names, (
        f"Ranked names for 'pro' wrong.\n expected {expected_names}\n got      {got_names}"
    )
    assert data["count"] == len(expected_names), (
        f"count for 'pro' should be {len(expected_names)} but got {data['count']}"
    )


def test_no_results(start_app):
    data = get_suggest("xyzzy")
    assert data["query"] == "xyzzy", f"query echoed wrong: {data['query']!r}"
    assert data["count"] == 0, f"count for no-match query should be 0 but got {data['count']}"
    assert data["results"] == [], f"results for no-match query should be [] but got {data['results']}"
    assert data["label"] == "No matches found", f"no-results label wrong: {data['label']!r}"


def test_limit_to_eight(start_app):
    products = load_products()
    products_by_name = {p["name"]: p for p in products}
    expected_names = [p["name"] for p in reference_rank("a", products)]
    assert len(expected_names) == 8, (
        "Test precondition: query 'a' should yield 8 results after truncation."
    )
    data = get_suggest("a")
    got_names = [r["name"] for r in data["results"]]
    assert len(got_names) == 8, f"Results for 'a' must be limited to 8 but got {len(got_names)}"
    assert got_names == expected_names, (
        f"Top-8 ranked names for 'a' wrong.\n expected {expected_names}\n got      {got_names}"
    )
    assert data["count"] == 8, f"count for 'a' should be 8 but got {data['count']}"
    assert data["label"] == "8 results", f"label for 'a' wrong: {data['label']!r}"
    _check_results_fields(data["results"], products_by_name)


def test_detail_endpoint(start_app):
    products_by_name = {p["name"]: p for p in load_products()}
    data = get_suggest("app")
    first = data["results"][0]
    assert first["name"] == "Apple", f"First 'app' suggestion should be Apple but was {first['name']!r}"
    pid = first["id"]

    resp = requests.get(f"{BACKEND_URL}/api/detail", params={"id": pid}, timeout=30)
    assert resp.status_code == 200, f"/api/detail?id={pid} returned {resp.status_code}"
    detail = resp.json()
    assert set(detail.keys()) == RESULT_KEYS, (
        f"detail object must have exactly keys {RESULT_KEYS} but had {set(detail.keys())}"
    )
    assert detail["id"] == pid, f"detail id mismatch: {detail['id']} vs {pid}"
    assert detail["name"] == "Apple", f"detail name mismatch: {detail['name']!r}"
    expected = products_by_name["Apple"]
    assert detail["category"] == expected["category"], "detail category mismatch for Apple"
    assert abs(float(detail["price"]) - expected["price"]) < 1e-6, "detail price mismatch for Apple"
    assert detail["description"] == expected["description"], "detail description mismatch for Apple"


def test_detail_not_found(start_app):
    resp = requests.get(f"{BACKEND_URL}/api/detail", params={"id": 999999}, timeout=30)
    assert resp.status_code == 404, (
        f"/api/detail?id=999999 should return 404 but returned {resp.status_code}"
    )


def test_frontend_page(start_app):
    resp = requests.get(FRONTEND_URL, timeout=30)
    assert resp.status_code == 200, f"Frontend returned status {resp.status_code}"
    body = resp.text
    for needle in ("Catalog Search", "Search products...", "Start typing to search the catalog"):
        assert needle in body, f"Frontend HTML is missing expected text: {needle!r}"


# --------------------------------------------------------------------------
# Browser test: the actual autocomplete UX.
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


def test_autocomplete_ux(start_app, browser_verifier):
    reason = (
        "The app is a typeahead autocomplete search over a product catalog. The empty "
        "search box should show a prompt, typing should show a ranked suggestion dropdown, "
        "and selecting a suggestion should fill the input and show that product's detail."
    )
    truth = (
        f"Navigate to {FRONTEND_URL}. Verify the empty-query prompt text "
        f"'Start typing to search the catalog' is visible and the search input has the "
        f"placeholder 'Search products...'. Click the search input and type 'app'. After a "
        f"short debounce, a dropdown list of suggestions appears whose first item is 'Apple', "
        f"and a label reading '6 results' is shown. Click the 'Apple' suggestion; the input "
        f"value becomes 'Apple' and a detail area shows the product's category 'Fruit' along "
        f"with its price and description. Then clear the input; the prompt "
        f"'Start typing to search the catalog' is shown again."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_autocomplete_ux",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
