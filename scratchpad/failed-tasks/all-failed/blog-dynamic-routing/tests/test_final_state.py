import os
import re
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = "/home/user/myproject"
EXCLUDED_DIRS = {".venv", "venv", ".web", "_export", "node_modules", "__pycache__", ".git"}

ROUTE_PATTERN = re.compile(
    r"""(?:@rx\.page\s*\(\s*[^)]*route\s*=\s*["']/posts/\[slug\]["']"""
    r"""|app\.add_page\s*\([^)]*route\s*=\s*["']/posts/\[slug\]["'])""",
    re.DOTALL,
)
ROUTER_PATTERN = re.compile(
    r"""router\.page\.params|router\.url|router\.route_id|router\.params"""
)
STATE_CLASS_PATTERN = re.compile(r"class\s+\w+\s*\(\s*(?:rx\.State|rx\.Base|reflex\.State)\b")
SLUG_LITERAL_PATTERN = re.compile(r"""['"]([a-zA-Z0-9][a-zA-Z0-9_\-]*)['"]""")


def _iter_py_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _read_all_python_sources():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist; the executor must create the Reflex app there."
    )
    files = list(_iter_py_files(PROJECT_DIR))
    assert files, f"No Python source files found under {PROJECT_DIR}."
    sources = {}
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                sources[path] = f.read()
        except (OSError, UnicodeDecodeError):
            continue
    return sources


def _find_posts_definitions(sources: dict[str, str]):
    """Locate hard-coded posts collections that declare slug + title fields.

    Returns a list of (slug, title) tuples extracted from any literal dict
    that contains both a `slug` key and a `title` key.
    """
    pair_pattern = re.compile(
        r"""\{\s*(?P<entries>(?:[^{}]|\{[^{}]*\})*?)\}""",
        re.DOTALL,
    )
    slug_key_pattern = re.compile(
        r"""(?:^|[,{\s])\s*["']?slug["']?\s*[:=]\s*["']([^"']+)["']""",
        re.MULTILINE,
    )
    title_key_pattern = re.compile(
        r"""(?:^|[,{\s])\s*["']?title["']?\s*[:=]\s*["']([^"']+)["']""",
        re.MULTILINE,
    )

    pairs: list[tuple[str, str]] = []
    for src in sources.values():
        for match in pair_pattern.finditer(src):
            block = match.group("entries")
            slug_match = slug_key_pattern.search(block)
            title_match = title_key_pattern.search(block)
            if slug_match and title_match:
                pairs.append((slug_match.group(1), title_match.group(1)))
    return pairs


@pytest.fixture(scope="module")
def project_sources():
    return _read_all_python_sources()


@pytest.fixture(scope="module")
def posts_pairs(project_sources):
    pairs = _find_posts_definitions(project_sources)
    assert pairs, (
        "Could not find any hardcoded posts collection containing both 'slug' and 'title' fields "
        "in the project's Python sources."
    )
    return pairs


def test_dynamic_route_registration_present(project_sources):
    matched_files = [path for path, src in project_sources.items() if ROUTE_PATTERN.search(src)]
    assert matched_files, (
        "Expected to find a page registered with route '/posts/[slug]' via "
        "@rx.page(route=\"/posts/[slug]\") or app.add_page(..., route=\"/posts/[slug]\"), "
        "but no such registration was found."
    )


def test_state_accesses_router_for_slug(project_sources):
    has_state_class = any(STATE_CLASS_PATTERN.search(src) for src in project_sources.values())
    assert has_state_class, (
        "Expected at least one class inheriting from rx.State to be defined in the project."
    )
    files_with_router_access = [
        path for path, src in project_sources.items() if ROUTER_PATTERN.search(src)
    ]
    assert files_with_router_access, (
        "Expected the project to access the dynamic slug via the Reflex router API "
        "(e.g., router.page.params or router.url), but no such access was found."
    )


def test_hardcoded_posts_have_three_unique_slugs(posts_pairs):
    slugs = [slug for slug, _title in posts_pairs]
    unique_slugs = []
    for s in slugs:
        if s not in unique_slugs:
            unique_slugs.append(s)
    assert len(unique_slugs) >= 3, (
        f"Expected the hardcoded posts collection to contain at least 3 unique slug literals, "
        f"found: {unique_slugs}"
    )
    # Detect the canonical 3-post collection: at least 3 distinct slugs paired with distinct titles.
    titles = {title for _slug, title in posts_pairs}
    assert len(titles) >= 3, (
        f"Expected at least 3 distinct post titles in the hardcoded collection, found: {titles}"
    )


def _run_reflex_export() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )


@pytest.fixture(scope="module")
def reflex_export_result():
    result = _run_reflex_export()
    yield result


def test_reflex_export_succeeds(reflex_export_result):
    assert reflex_export_result.returncode == 0, (
        "`uv run reflex export --frontend-only --no-zip` failed.\n"
        f"stdout:\n{reflex_export_result.stdout}\n"
        f"stderr:\n{reflex_export_result.stderr}"
    )


def test_dynamic_route_page_generated(reflex_export_result):
    assert reflex_export_result.returncode == 0, (
        "Skipping generated-page check because the reflex export command failed."
    )
    candidates = [
        Path(PROJECT_DIR) / ".web" / "pages" / "posts" / "[slug].js",
        Path(PROJECT_DIR) / ".web" / "pages" / "posts" / "[slug].jsx",
        Path(PROJECT_DIR) / ".web" / "pages" / "posts" / "[slug].tsx",
        Path(PROJECT_DIR) / ".web" / ".next" / "server" / "pages" / "posts" / "[slug].html",
        Path(PROJECT_DIR) / ".web" / ".next" / "server" / "pages" / "posts" / "[slug].js",
    ]
    for candidate in candidates:
        if candidate.exists():
            return

    # Fallback: glob search for any generated artifact for posts/[slug] under .web or _export.
    search_roots = [Path(PROJECT_DIR) / ".web", Path(PROJECT_DIR) / "_export"]
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and "posts" in path.parts:
                # accept either the literal [slug] segment or pre-rendered slug subpaths
                if "[slug]" in path.name or any(part == "[slug]" for part in path.parts):
                    return

    raise AssertionError(
        "Could not find a generated Next.js page file for the dynamic route 'posts/[slug]' "
        "after running `reflex export --frontend-only --no-zip`. "
        f"Checked candidates: {[str(c) for c in candidates]}"
    )


def test_post_title_appears_in_build_output(reflex_export_result, posts_pairs):
    assert reflex_export_result.returncode == 0, (
        "Skipping build-output title check because the reflex export command failed."
    )
    titles = {title for _slug, title in posts_pairs}
    search_roots = [
        Path(PROJECT_DIR) / ".web",
        Path(PROJECT_DIR) / "_export",
    ]
    found_title = None
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".js", ".jsx", ".tsx", ".ts", ".html", ".json", ".txt", ".css", ".mjs"}:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for title in titles:
                if title and title in content:
                    found_title = title
                    break
            if found_title:
                break
        if found_title:
            break

    assert found_title is not None, (
        "Expected the literal title of at least one of the hardcoded posts "
        f"({sorted(titles)}) to appear in the Reflex build output under .web/ or _export/, "
        "but none was found."
    )


def test_no_reflex_servers_remaining():
    """Make sure no leftover reflex/uvicorn/next dev servers are running after verification."""
    result = subprocess.run(
        ["pgrep", "-fa", r"reflex run|next dev|uvicorn .*reflex"],
        capture_output=True,
        text=True,
    )
    # pgrep exits 1 when there is no match; that is the desired state.
    if result.returncode == 0 and result.stdout.strip():
        # Attempt cleanup so subsequent tests in the same harness are not affected.
        subprocess.run(["pkill", "-f", "reflex run"], capture_output=True)
        subprocess.run(["pkill", "-f", "next dev"], capture_output=True)
        subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
        raise AssertionError(
            "Expected no leftover Reflex/Next/uvicorn dev servers after task completion, "
            f"but found:\n{result.stdout}"
        )
