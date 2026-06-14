import os
import re
import socket
import subprocess

import pytest
from xprocess import ProcessStarter
from pochi_verifier import PochiVerifier


PROJECT_DIR = "/home/user/myproject"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000


# ---------------------------------------------------------------------------
# Static (filesystem / source code) checks — do not need the running server.
# ---------------------------------------------------------------------------


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected the Reflex project to exist at {PROJECT_DIR}, but the directory is missing."
    )


def test_reflex_project_initialized():
    rxconfig_path = os.path.join(PROJECT_DIR, "rxconfig.py")
    assert os.path.isfile(rxconfig_path), (
        f"Expected a Reflex project config at {rxconfig_path}; the project does not appear to be "
        f"initialized with `reflex init`."
    )


def test_markdown_it_py_declared_as_dependency():
    candidate_files = [
        os.path.join(PROJECT_DIR, "pyproject.toml"),
        os.path.join(PROJECT_DIR, "requirements.txt"),
    ]
    seen_any = False
    for path in candidate_files:
        if not os.path.isfile(path):
            continue
        seen_any = True
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read().lower()
        if "markdown-it-py" in content or "markdown_it_py" in content:
            return
    assert seen_any, (
        f"Neither pyproject.toml nor requirements.txt was found under {PROJECT_DIR}; cannot "
        f"verify that `markdown-it-py` is a declared dependency."
    )
    raise AssertionError(
        "`markdown-it-py` is not declared as a dependency in pyproject.toml or requirements.txt; "
        "the task requires this package to render Markdown server-side."
    )


def test_cached_computed_var_used_for_markdown_conversion():
    cache_pattern = re.compile(r"@(?:rx|reflex)\.var\(\s*cache\s*=\s*True\s*\)")
    md_import_pattern = re.compile(r"\b(?:from\s+markdown_it|import\s+markdown_it|markdown_it_py)\b")
    found_cache = False
    found_md_import = False
    for root, _dirs, files in os.walk(PROJECT_DIR):
        # Skip generated/.venv directories to avoid false positives or expensive scans.
        if any(part in {".venv", ".web", "node_modules", "__pycache__"} for part in root.split(os.sep)):
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            full = os.path.join(root, fname)
            try:
                with open(full, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            if not found_cache and cache_pattern.search(text):
                found_cache = True
            if not found_md_import and md_import_pattern.search(text):
                found_md_import = True
            if found_cache and found_md_import:
                return
    assert found_cache, (
        "Did not find any `@rx.var(cache=True)` (or `@reflex.var(cache=True)`) annotation in the "
        "Reflex project's Python sources; the Markdown preview must be implemented as a cached "
        "computed var."
    )
    assert found_md_import, (
        "Did not find any import of `markdown_it` in the Reflex project's Python sources; the "
        "preview must convert Markdown using markdown-it-py."
    )


# ---------------------------------------------------------------------------
# Long-running app fixture (starts the Reflex dev/prod server).
# ---------------------------------------------------------------------------


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="session")
def start_reflex_app(xprocess):
    # Best-effort: kill any straggler reflex/next processes from a prior run so we get
    # a clean bind on ports 3000/8000.
    for cmd in (
        ["pkill", "-f", "reflex run"],
        ["pkill", "-f", "next-server"],
        ["pkill", "-f", "uvicorn"],
    ):
        subprocess.run(cmd, capture_output=True, check=False)

    class Starter(ProcessStarter):
        name = "reflex_app"
        args = ["uv", "run", "reflex", "run", "--env", "prod", "--loglevel", "info"]
        env = os.environ.copy()
        popen_kwargs = {
            "cwd": PROJECT_DIR,
            "text": True,
        }
        timeout = 600  # The first `reflex run` compiles the Next.js frontend; allow time.
        terminate_on_interrupt = True

        def startup_check(self):
            # Both the backend (8000) and the frontend (3000) must be listening before
            # the app is usable. Wait for both.
            return _port_open(FRONTEND_PORT) and _port_open(BACKEND_PORT)

    xprocess.ensure(Starter.name, Starter)

    yield

    info = xprocess.getinfo(Starter.name)
    info.terminate()

    # Belt-and-braces cleanup — make sure no Reflex-related processes are left holding the
    # ports for subsequent tests or task runs.
    for cmd in (
        ["pkill", "-f", "reflex run"],
        ["pkill", "-f", "next-server"],
        ["pkill", "-f", "uvicorn"],
    ):
        subprocess.run(cmd, capture_output=True, check=False)


# ---------------------------------------------------------------------------
# Browser-driven verification (one focused PochiVerifier call per criterion).
# ---------------------------------------------------------------------------


def test_page_loads_with_required_dom_hooks(start_reflex_app):
    reason = (
        "The Reflex page must render with the stable DOM hooks the task contract requires: a "
        "textarea for the Markdown source, a preview container, a counter element, and three "
        "toolbar buttons."
    )
    truth = (
        "Navigate to http://localhost:3000/. Wait until the page finishes loading. Verify, "
        "using DOM inspection (for example by evaluating `document.getElementById('<id>')` for "
        "each id in the developer tools), that ALL of the following elements exist on the page: "
        "a `<textarea>` element with id `md-source`, an element with id `md-preview`, an element "
        "with id `md-counter`, a button with id `btn-bold`, a button with id `btn-italic`, and a "
        "button with id `btn-code`. The test passes only if every one of these six ids resolves "
        "to a real element."
    )
    verifier = PochiVerifier()
    result = verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_page_loads_with_required_dom_hooks",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_counter_displays_correctly_for_empty_and_known_input(start_reflex_app):
    reason = (
        "The counter element must reactively show word and character counts of the textarea's "
        "current contents in the exact format `Words: <N> | Characters: <M>`."
    )
    truth = (
        "Navigate to http://localhost:3000/. Locate the textarea with id `md-source` and the "
        "counter element with id `md-counter`. "
        "STEP A (empty input): Programmatically clear the textarea (set its value to the empty "
        "string and dispatch `input` and `change` events on it so Reflex's state syncs). Wait up "
        "to 10 seconds, then read the visible text of `#md-counter`. It must equal exactly "
        "`Words: 0 | Characters: 0`. "
        "STEP B (known input): Programmatically set the textarea value to the string "
        "`the quick brown fox` (19 characters, 4 words) and dispatch `input` and `change` events. "
        "Wait up to 10 seconds, then read the visible text of `#md-counter`. It must equal "
        "exactly `Words: 4 | Characters: 19`. The test passes only if BOTH steps observe the "
        "exact expected counter text."
    )
    verifier = PochiVerifier()
    result = verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_counter_displays_correctly",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_markdown_preview_renders_expected_html(start_reflex_app):
    reason = (
        "The HTML preview must reactively reflect the result of converting the textarea's "
        "Markdown source to HTML via markdown-it-py and injecting it through `rx.html`."
    )
    truth = (
        "Navigate to http://localhost:3000/. For EACH of the following Markdown inputs, "
        "programmatically set the textarea `#md-source` value to that input and dispatch `input` "
        "and `change` events so Reflex syncs state. Then wait up to 10 seconds for the preview "
        "container `#md-preview` to update, and verify its inner HTML contains the required "
        "substrings:\n"
        "1. Input `# Heading` → `#md-preview` innerHTML must contain an `<h1` tag whose text "
        "content includes `Heading` and the matching `</h1>` closing tag.\n"
        "2. Input `**bold**` → `#md-preview` innerHTML must contain the exact substring "
        "`<strong>bold</strong>`.\n"
        "3. Input `*italic*` → `#md-preview` innerHTML must contain the exact substring "
        "`<em>italic</em>`.\n"
        "4. Input `` `code` `` (literal backtick-code-backtick) → `#md-preview` innerHTML must "
        "contain the exact substring `<code>code</code>`.\n"
        "5. Input `- a\\n- b` (a two-item unordered list, with a real newline between the two "
        "items) → `#md-preview` innerHTML must contain `<ul>`, `<li>a</li>`, and `<li>b</li>`.\n"
        "The test passes only if EVERY one of the five inputs produces a preview that contains "
        "ALL of its required substrings."
    )
    verifier = PochiVerifier()
    result = verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_markdown_preview_renders_expected_html",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_toolbar_wraps_selection_with_markdown_markers(start_reflex_app):
    reason = (
        "The Bold/Italic/Code toolbar buttons must wrap the textarea's currently selected "
        "substring with the appropriate Markdown markers by mutating the backend state, and "
        "the change must be reflected back into the controlled textarea value."
    )
    truth = (
        "Navigate to http://localhost:3000/. Throughout this test, use the textarea with id "
        "`md-source` and the buttons with ids `btn-bold`, `btn-italic`, `btn-code`. After each "
        "step, wait up to 10 seconds for the textarea's `value` property to update before "
        "asserting.\n"
        "STEP A — Bold over a selected word: Set the textarea value to `hello world`. Dispatch "
        "`input` and `change` events. Then call `textarea.focus(); textarea.setSelectionRange(0, 5);` "
        "and dispatch a `select` event on the textarea so the backend records the selection "
        "range covering the word `hello`. Click `#btn-bold`. The textarea's `value` property "
        "must become exactly `**hello** world`.\n"
        "STEP B — Italic over a selected word: Set the textarea value back to `hello world`, "
        "dispatch `input`/`change`, then `setSelectionRange(6, 11)` and dispatch `select` to "
        "select the word `world`. Click `#btn-italic`. The textarea's value must become exactly "
        "`hello *world*`.\n"
        "STEP C — Code over the whole content: Set the textarea value to `print(x)`, dispatch "
        "`input`/`change`, then `setSelectionRange(0, 8)` and dispatch `select`. Click "
        "`#btn-code`. The textarea's value must become exactly `` `print(x)` `` (the literal "
        "8 characters: a backtick, `print(x)`, then a backtick).\n"
        "STEP D — Empty selection at end of content: Set the textarea value to `abc`, dispatch "
        "`input`/`change`, then `setSelectionRange(3, 3)` and dispatch `select` (zero-width "
        "selection at position 3). Click `#btn-bold`. The textarea's value must become exactly "
        "`abc****` (the three letters followed by four backtick-free asterisks).\n"
        "The test passes only if ALL FOUR steps produce the exact expected textarea value."
    )
    verifier = PochiVerifier()
    result = verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_toolbar_wraps_selection",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"


def test_preview_html_is_cached_against_selection_changes(start_reflex_app):
    reason = (
        "Because the preview HTML is produced by a cached computed var that only depends on the "
        "Markdown source, changing the textarea selection (without changing the source text) "
        "must not change the rendered preview."
    )
    truth = (
        "Navigate to http://localhost:3000/. Set the textarea `#md-source` value to `# Heading`, "
        "dispatch `input` and `change` events, and wait up to 10 seconds for `#md-preview` to "
        "render the heading (its innerHTML should contain `<h1` and the text `Heading`). "
        "Read and record the full innerHTML string of `#md-preview`; call it HTML_BEFORE. "
        "Without changing the textarea value, programmatically call "
        "`textarea.focus(); textarea.setSelectionRange(0, 1);` and dispatch a `select` event so "
        "the backend receives an updated selection range. Wait at least 3 seconds. Read the "
        "innerHTML of `#md-preview` again; call it HTML_AFTER. The test passes ONLY if "
        "HTML_BEFORE is exactly equal (character-for-character) to HTML_AFTER, demonstrating "
        "that the cached computed var did not recompute when only the selection changed."
    )
    verifier = PochiVerifier()
    result = verifier.verify(
        reason=reason,
        truth=truth,
        use_browser_agent=True,
        trajectory_dir="/logs/verifier/pochi/test_preview_html_is_cached",
    )
    assert result.status == "pass", f"Browser verification failed: {result.reason}"
