FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        build-essential unzip procps && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv (Astral) into /usr/local/bin so reflex's uv-managed workflow works.
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh && \
    /usr/local/bin/uv --version

RUN mkdir -p /home/user && chmod 0755 /home/user

# Scaffold the Reflex project the way the research plan describes:
#   uv init && uv add reflex && uv run reflex init --template blank
# The blank template produces a minimal project under ./myproject with the
# state class boilerplate that the agent has to replace.
RUN mkdir -p /home/user/myproject && \
    cd /home/user/myproject && \
    uv init --name myproject --no-readme --no-workspace --no-pin-python && \
    uv add reflex && \
    uv run reflex init --template blank && \
    uv run python -c "import reflex; print('reflex', reflex.__version__)"

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex search-filter-computed task: scaffolded Reflex blank-template project at /home/user/myproject managed by uv, with Node.js 24 for the Next.js build."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v24 (required by Reflex to build its Next.js frontend)
#   - uv (Astral) installed in /usr/local/bin
#   - /home/user/myproject: uv-managed Reflex blank-template project
