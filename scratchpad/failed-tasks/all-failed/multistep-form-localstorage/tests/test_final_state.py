import os
import re
import socket
import subprocess
from pathlib import Path

import pytest


PROJECT_DIR = "/home/user/myproject"
APP_PACKAGE_DIR = os.path.join(PROJECT_DIR, "multistep_form")
WEB_DIR = os.path.join(PROJECT_DIR, ".web")

REQUIRED_FIELDS = [
    "name",
    "email",
    "address",
    "city",
    "password",
    "confirm_password",
]


def _read_app_sources() -> str:
    """Read and concatenate every .py file in the Reflex application package.

    The agent may organize their state across multiple files. We aggregate them
    all for the AST/regex source-level checks described in the task truth.
    """
    package = Path(APP_PACKAGE_DIR)
    assert package.is_dir(), (
        f"Expected the Reflex application package directory at {APP_PACKAGE_DIR}."
    )
    sources = []
    for py_file in package.rglob("*.py"):
        try:
            sources.append(py_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    combined = "\n\n# === FILE BOUNDARY ===\n\n".join(sources)
    assert combined.strip(), (
        f"No readable Python source found under {APP_PACKAGE_DIR}."
    )
    return combined


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="session")
def app_sources() -> str:
    return _read_app_sources()


@pytest.fixture(scope="session")
def exported_frontend() -> Path:
    """Ensure the Reflex frontend has been exported and return its path.

    `uv run reflex export --frontend-only --no-zip` produces a compiled Next.js
    project under `.web/`. The verifier greps that directory for the rendered
    input names.
    """
    web_dir = Path(WEB_DIR)
    if not web_dir.is_dir() or not any(web_dir.rglob("*")):
        result = subprocess.run(
            ["uv", "run", "reflex", "export", "--frontend-only", "--no-zip"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, (
            "`uv run reflex export --frontend-only --no-zip` failed.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    assert web_dir.is_dir(), (
        f"Expected the exported frontend to be present at {WEB_DIR}."
    )
    return web_dir


# ---------------------------------------------------------------------------
# 1. State definition checks
# ---------------------------------------------------------------------------


def test_state_has_step_var(app_sources: str):
    assert re.search(r"\bstep\s*:\s*int\s*=\s*1\b", app_sources), (
        "Expected the state to declare `step: int = 1`."
    )


def test_state_has_submitted_var(app_sources: str):
    assert re.search(r"\bsubmitted\s*:\s*bool\s*=\s*False\b", app_sources), (
        "Expected the state to declare `submitted: bool = False`."
    )


def test_state_uses_at_least_six_local_storage_fields(app_sources: str):
    matches = re.findall(r"rx\.LocalStorage\s*\(", app_sources)
    assert len(matches) >= 6, (
        f"Expected at least 6 `rx.LocalStorage(` declarations, found {len(matches)}."
    )


def test_local_storage_names_cover_all_required_fields(app_sources: str):
    # Capture the entire argument list of every rx.LocalStorage(...) call, then
    # look for the explicit `name="<field>"` keyword argument inside it.
    call_pattern = re.compile(r"rx\.LocalStorage\s*\((?P<args>[^)]*)\)")
    name_pattern = re.compile(r"name\s*=\s*['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*)['\"]")

    observed_names = set()
    explicit_name_calls = 0
    for match in call_pattern.finditer(app_sources):
        args = match.group("args")
        name_match = name_pattern.search(args)
        if name_match:
            explicit_name_calls += 1
            observed_names.add(name_match.group("name"))

    assert explicit_name_calls >= 6, (
        "Expected at least 6 `rx.LocalStorage(...)` calls to pass an explicit "
        f"`name=` keyword argument, found {explicit_name_calls}."
    )

    missing = [field for field in REQUIRED_FIELDS if field not in observed_names]
    assert not missing, (
        "Expected `rx.LocalStorage(..., name=...)` declarations covering every "
        f"required field; missing names: {missing}. Observed names: {sorted(observed_names)}."
    )


# ---------------------------------------------------------------------------
# 2. Event handler checks
# ---------------------------------------------------------------------------


def test_event_handlers_next_and_prev_step_exist(app_sources: str):
    assert re.search(r"def\s+next_step\s*\(\s*self", app_sources), (
        "Expected an event handler `def next_step(self, ...)` on the state class."
    )
    assert re.search(r"def\s+prev_step\s*\(\s*self", app_sources), (
        "Expected an event handler `def prev_step(self, ...)` on the state class."
    )


def test_event_handlers_mutate_step(app_sources: str):
    # The handlers must touch `self.step` somewhere in their bodies.
    next_block = re.search(
        r"def\s+next_step\s*\(\s*self[^)]*\)\s*:(?P<body>.*?)(?=\n\s*def\s|\Z)",
        app_sources,
        flags=re.DOTALL,
    )
    prev_block = re.search(
        r"def\s+prev_step\s*\(\s*self[^)]*\)\s*:(?P<body>.*?)(?=\n\s*def\s|\Z)",
        app_sources,
        flags=re.DOTALL,
    )
    assert next_block and "self.step" in next_block.group("body"), (
        "`next_step` must mutate or reference `self.step`."
    )
    assert prev_block and "self.step" in prev_block.group("body"), (
        "`prev_step` must mutate or reference `self.step`."
    )


def test_step_bounds_are_enforced(app_sources: str):
    # We require both upper bound (3) and lower bound (1) to appear inside the
    # bodies of the next_step / prev_step handlers, either as explicit numeric
    # comparisons or via min/max clamps.
    next_block = re.search(
        r"def\s+next_step\s*\(\s*self[^)]*\)\s*:(?P<body>.*?)(?=\n\s*def\s|\Z)",
        app_sources,
        flags=re.DOTALL,
    )
    prev_block = re.search(
        r"def\s+prev_step\s*\(\s*self[^)]*\)\s*:(?P<body>.*?)(?=\n\s*def\s|\Z)",
        app_sources,
        flags=re.DOTALL,
    )
    assert next_block is not None, "Could not locate next_step body."
    assert prev_block is not None, "Could not locate prev_step body."

    next_body = next_block.group("body")
    prev_body = prev_block.group("body")

    assert re.search(r"\b3\b", next_body), (
        "`next_step` must enforce an upper bound of 3 (e.g. `if self.step < 3` or `min(..., 3)`)."
    )
    assert re.search(r"\b1\b", prev_body), (
        "`prev_step` must enforce a lower bound of 1 (e.g. `if self.step > 1` or `max(..., 1)`)."
    )


def test_final_submit_validates_passwords_and_clears_storage(app_sources: str):
    # Find any handler body that flips submitted to True; require the password
    # equality check and the clearing of all six LocalStorage fields nearby.
    submit_handlers = re.findall(
        r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*self[^)]*\)\s*:(?P<body>(?:.|\n)*?)(?=\n\s*def\s|\Z)",
        app_sources,
    )
    matching_body = None
    for _name, body in submit_handlers:
        if "self.submitted" in body and "True" in body:
            matching_body = body
            break

    assert matching_body is not None, (
        "Expected at least one event handler that sets `self.submitted = True`."
    )

    assert (
        "self.password" in matching_body
        and "self.confirm_password" in matching_body
        and "==" in matching_body
    ), (
        "The final-submit handler must compare `self.password == self.confirm_password` "
        "before setting `self.submitted = True`."
    )

    # The handler must clear every LocalStorage-backed field by assigning "".
    for field in REQUIRED_FIELDS:
        assert re.search(
            rf"self\.{field}\s*=\s*['\"]\s*['\"]", matching_body
        ), (
            f"Expected the final-submit handler to reset `self.{field}` to an empty string."
        )


# ---------------------------------------------------------------------------
# 3. Frontend export checks
# ---------------------------------------------------------------------------


def test_exported_frontend_contains_all_field_names(exported_frontend: Path):
    candidate_dirs = [exported_frontend / "pages", exported_frontend / "utils", exported_frontend]
    contents_blob_parts: list[str] = []
    for candidate in candidate_dirs:
        if not candidate.exists():
            continue
        for path in candidate.rglob("*"):
            if path.is_file() and path.suffix in {".js", ".jsx", ".ts", ".tsx", ".html"}:
                try:
                    contents_blob_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    continue

    blob = "\n".join(contents_blob_parts)
    assert blob.strip(), (
        f"Could not read any exported frontend files under {exported_frontend}."
    )

    missing = []
    for field in REQUIRED_FIELDS:
        # Accept the field name appearing as a quoted string (used by Reflex as
        # the input `name` attribute or storage key).
        if not re.search(rf'["\']{re.escape(field)}["\']', blob):
            missing.append(field)
    assert not missing, (
        f"Exported frontend is missing references to required field names: {missing}."
    )


# ---------------------------------------------------------------------------
# 4. Cleanliness check
# ---------------------------------------------------------------------------


def test_ports_are_free():
    busy = [port for port in (3000, 8000) if _port_in_use(port)]
    assert not busy, (
        f"Expected no leftover Reflex servers, but the following ports are still in use: {busy}. "
        "Make sure all background servers are killed at the end of the task."
    )
