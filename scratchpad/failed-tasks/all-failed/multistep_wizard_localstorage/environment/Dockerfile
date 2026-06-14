FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        sqlite3 build-essential unzip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages pytest-json-ctrf requests pytest-xprocess && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex multi-step wizard task environment with uv, Node.js v24, sqlite3, and pytest verification tooling."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: sqlite3 (DB verification), build-essential (native Python deps), unzip
#   - Node.js v24 (required by Reflex to compile the Next.js frontend)
#   - Astral uv installed via the official installer with symlinks in /usr/local/bin
#   - always required pip3 packages: pytest-json-ctrf
#   - extra pip3 packages: requests (HTTP verification), pytest-xprocess (long-running server fixture)
#   - /home/user: workspace root; the executor creates /home/user/wizard_app inside the task
