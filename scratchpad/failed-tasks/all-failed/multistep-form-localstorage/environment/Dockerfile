FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep unzip xz-utils && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-scaffold the Reflex project using uv + the official non-interactive
# blank template so the executor has a clean starting point matching the
# initial state tests.
RUN mkdir -p /home/user/myproject && \
    cd /home/user/myproject && \
    uv init --name multistep_form && \
    uv add reflex && \
    uv run reflex init --template blank

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex multi-step form wizard task environment with uv-managed Python project and Node.js v24."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v24 (required by the Reflex frontend export tooling)
#   - uv (Astral) for managing the Python environment
#   - /home/user/myproject: uv-managed Reflex project scaffolded with the blank template
