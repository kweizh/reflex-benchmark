FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        unzip xz-utils build-essential psmisc procps lsof sqlite3 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        pytest-xprocess \
        requests && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex Kanban task environment: uv-managed Reflex project with FastAPI api_transformer move endpoint and SQLite persistence; Node.js v24 for Next.js, sqlite3 CLI and pytest-xprocess/requests for DB-level final-state verification."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: unzip xz-utils build-essential psmisc procps lsof sqlite3 (needed by uv/reflex/node, process cleanup, and direct SQLite inspection from the verifier)
#   - always required pip3 packages: pytest-json-ctrf
#   - pip3 packages for verification: pytest-xprocess, requests (used by tests/test_final_state.py to start the reflex server and hit the move API)
#   - Node.js v24: required by Reflex to build the Next.js frontend
#   - uv (Astral): used by the executor to manage the Reflex Python environment via `uv run`
#   - /home/user: working directory; the executor creates /home/user/kanban_drag_drop_persistence
