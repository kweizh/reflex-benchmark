FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        sqlite3 psmisc unzip xz-utils build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf requests pytest-xprocess && \
    curl -fsSL https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex realtime multi-room chat task environment with uv, Node.js v24, and SQLite."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - sqlite3 CLI for inspecting the Reflex SQLite database during verification
#   - psmisc for `fuser` to free Reflex backend/frontend ports between runs
#   - unzip / xz-utils / build-essential needed by Reflex's bundled bun and Node-based frontend toolchain
#   - Node.js v24 for the Reflex frontend (Next.js) compile/runtime
#   - `uv` package manager installed system-wide so the agent can manage the Reflex project per plan.md
#   - pip3: requests + pytest-xprocess used by the final-state verifier
#   - /home/user: home directory; the agent will create /home/user/myproject during the task
