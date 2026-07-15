import os
import socket
import sqlite3

import pytest
import requests
from pochi_verifier import PochiVerifier
from xprocess import ProcessStarter

PROJECT_DIR = "/home/user/threaded_comments"
DB_PATH = os.path.join(PROJECT_DIR, "reflex.db")

# Always use the IPv4 loopback explicitly. Node/Next.js dev servers may bind only
# the IPv6 loopback (::1) when "localhost" is used, which would make an AF_INET
# readiness check hang for the whole timeout.
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0


@pytest.fixture(scope="session")
def browser_verifier():
    return PochiVerifier()


@pytest.fixture(scope="session")
def start_app(xprocess):
    """Start the Reflex dev server (frontend on 3000, backend on 8000)."""
    # Start from a clean database so the app reports an empty state initially.
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

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
            if not _port_open(BACKEND_PORT) or not _port_open(FRONTEND_PORT):
                return False
            # Backend health endpoint must answer with "pong".
            try:
                ping = requests.get(f"{BACKEND_URL}/ping/", timeout=20)
                if ping.status_code >= 500 or "pong" not in ping.text.lower():
                    return False
            except requests.RequestException:
                return False
            # Frontend must respond (first request triggers on-demand bundling).
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
        except FileNotFoundError:
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


def _post_comment(author, body, parent_id):
    return requests.post(
        f"{BACKEND_URL}/api/comments",
        json={"author": author, "body": body, "parent_id": parent_id},
        timeout=30,
    )


def _upvote(comment_id):
    return requests.post(
        f"{BACKEND_URL}/api/comments/{comment_id}/upvote", timeout=30
    )


@pytest.fixture(scope="session")
def populated(start_app):
    """Drive the app through the JSON API and return the created comment ids."""
    # Empty start.
    stats = requests.get(f"{BACKEND_URL}/api/stats", timeout=30)
    assert stats.status_code == 200, f"/api/stats returned {stats.status_code}"
    assert stats.json().get("total_comments") == 0, (
        f"Expected an empty board at start, got {stats.json()}"
    )

    # Create the thread: A (root) -> B -> C, plus D (root).
    ra = _post_comment("alice", "Root one", None)
    assert ra.status_code == 201, f"Create root A failed: {ra.status_code} {ra.text}"
    a = ra.json()["id"]

    rb = _post_comment("bob", "Reply to one", a)
    assert rb.status_code == 201, f"Create reply B failed: {rb.status_code} {rb.text}"
    b = rb.json()["id"]

    rc = _post_comment("carol", "Nested reply", b)
    assert rc.status_code == 201, f"Create reply C failed: {rc.status_code} {rc.text}"
    c = rc.json()["id"]

    rd = _post_comment("dave", "Root two", None)
    assert rd.status_code == 201, f"Create root D failed: {rd.status_code} {rd.text}"
    d = rd.json()["id"]

    # Invalid parent must be rejected and must not create a row.
    bad = _post_comment("erin", "orphan", 999999)
    assert bad.status_code == 404, (
        f"Posting with a non-existent parent must return 404, got {bad.status_code}"
    )

    # Upvotes.
    for _ in range(2):
        r = _upvote(a)
        assert r.status_code == 200, f"Upvote A failed: {r.status_code} {r.text}"
    assert r.json()["votes"] == 2, f"A should have 2 votes, got {r.json()}"

    r = _upvote(b)
    assert r.status_code == 200, f"Upvote B failed: {r.status_code} {r.text}"
    assert r.json()["votes"] == 1, f"B should have 1 vote, got {r.json()}"

    for _ in range(3):
        r = _upvote(c)
        assert r.status_code == 200, f"Upvote C failed: {r.status_code} {r.text}"
    assert r.json()["votes"] == 3, f"C should have 3 votes, got {r.json()}"

    for _ in range(5):
        r = _upvote(d)
        assert r.status_code == 200, f"Upvote D failed: {r.status_code} {r.text}"
    assert r.json()["votes"] == 5, f"D should have 5 votes, got {r.json()}"

    return {"a": a, "b": b, "c": c, "d": d}


def test_stats_reflects_total(populated):
    stats = requests.get(f"{BACKEND_URL}/api/stats", timeout=30)
    assert stats.status_code == 200, f"/api/stats returned {stats.status_code}"
    assert stats.json().get("total_comments") == 4, (
        f"Expected total_comments == 4, got {stats.json()}"
    )


def test_upvote_missing_returns_404(populated):
    r = _upvote(999999)
    assert r.status_code == 404, (
        f"Upvoting a non-existent comment must return 404, got {r.status_code}"
    )


def _node_keys_ok(node):
    return set(node.keys()) == {"id", "author", "body", "votes", "score", "children"}


def test_nested_tree_and_scores(populated):
    ids = populated
    resp = requests.get(f"{BACKEND_URL}/api/comments", timeout=30)
    assert resp.status_code == 200, f"/api/comments returned {resp.status_code}"
    roots = resp.json()
    assert isinstance(roots, list) and len(roots) == 2, (
        f"Expected exactly 2 root nodes, got {roots}"
    )

    root_a, root_d = roots[0], roots[1]

    # Roots ordered by ascending id: A then D.
    assert root_a["id"] == ids["a"], f"First root should be A, got {root_a}"
    assert root_d["id"] == ids["d"], f"Second root should be D, got {root_d}"

    for node in (root_a, root_d):
        assert _node_keys_ok(node), f"Node has wrong keys: {sorted(node.keys())}"

    # Structure: A -> B -> C.
    assert root_a["author"] == "alice", f"Root A author mismatch: {root_a}"
    assert root_a["votes"] == 2, f"Root A votes mismatch: {root_a}"
    assert len(root_a["children"]) == 1, f"A should have exactly 1 child: {root_a}"

    node_b = root_a["children"][0]
    assert _node_keys_ok(node_b), f"Node B has wrong keys: {sorted(node_b.keys())}"
    assert node_b["id"] == ids["b"], f"A's child should be B: {node_b}"
    assert node_b["author"] == "bob", f"Node B author mismatch: {node_b}"
    assert node_b["votes"] == 1, f"Node B votes mismatch: {node_b}"
    assert len(node_b["children"]) == 1, f"B should have exactly 1 child: {node_b}"

    node_c = node_b["children"][0]
    assert _node_keys_ok(node_c), f"Node C has wrong keys: {sorted(node_c.keys())}"
    assert node_c["id"] == ids["c"], f"B's child should be C: {node_c}"
    assert node_c["author"] == "carol", f"Node C author mismatch: {node_c}"
    assert node_c["votes"] == 3, f"Node C votes mismatch: {node_c}"
    assert node_c["children"] == [], f"C should have no children: {node_c}"

    # Root D is separate.
    assert root_d["author"] == "dave", f"Root D author mismatch: {root_d}"
    assert root_d["votes"] == 5, f"Root D votes mismatch: {root_d}"
    assert root_d["children"] == [], f"D should have no children: {root_d}"

    # Score = own votes + subtree votes of all descendants.
    assert node_c["score"] == 3, f"C score should be 3, got {node_c['score']}"
    assert node_b["score"] == 4, f"B score should be 4 (1+3), got {node_b['score']}"
    assert root_a["score"] == 6, f"A score should be 6 (2+4), got {root_a['score']}"
    assert root_d["score"] == 5, f"D score should be 5, got {root_d['score']}"


def _find_comment_table(conn):
    """Locate the comment table by its column shape (author, body, votes, parent)."""
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    for table in tables:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
        lower = {c.lower() for c in cols}
        parent_col = next((c for c in cols if "parent" in c.lower()), None)
        if {"author", "body", "votes"}.issubset(lower) and parent_col:
            return table, parent_col
    raise AssertionError(
        f"Could not find a comment table (author/body/votes/parent) among: {tables}"
    )


def test_persisted_in_sqlite(populated):
    ids = populated
    assert os.path.isfile(DB_PATH), f"SQLite database not found at {DB_PATH}"

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    try:
        table, parent_col = _find_comment_table(conn)
        rows = conn.execute(
            f'SELECT id, "{parent_col}", votes FROM "{table}"'
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 4, f"Expected exactly 4 persisted comment rows, got {len(rows)}"

    by_id = {r[0]: {"parent": r[1], "votes": r[2]} for r in rows}
    for key in ("a", "b", "c", "d"):
        assert ids[key] in by_id, f"Comment {key} (id={ids[key]}) missing from DB"

    assert by_id[ids["a"]]["parent"] is None, "Root A must have a NULL parent id"
    assert by_id[ids["d"]]["parent"] is None, "Root D must have a NULL parent id"
    assert by_id[ids["b"]]["parent"] == ids["a"], "B's parent must be A"
    assert by_id[ids["c"]]["parent"] == ids["b"], "C's parent must be B"

    assert by_id[ids["a"]]["votes"] == 2, "A must have 2 persisted votes"
    assert by_id[ids["b"]]["votes"] == 1, "B must have 1 persisted vote"
    assert by_id[ids["c"]]["votes"] == 3, "C must have 3 persisted votes"
    assert by_id[ids["d"]]["votes"] == 5, "D must have 5 persisted votes"


def test_frontend_renders_page(start_app, browser_verifier):
    reason = (
        "The Reflex app must serve a threaded comment board UI on its homepage that "
        "renders a nested comment tree and shows a total comment count."
    )
    truth = (
        f"Navigate to {FRONTEND_URL}. Verify the page loads successfully and its "
        "content includes the heading text 'Threaded Comments'."
    )
    result = browser_verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_frontend_renders_page",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
