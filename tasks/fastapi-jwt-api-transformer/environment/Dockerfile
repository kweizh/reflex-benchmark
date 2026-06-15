FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep build-essential unzip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf requests && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv (Astral) for managing the Reflex Python environment.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx

RUN mkdir -p /home/user && chmod 0755 /home/user

# Bootstrap a blank Reflex project under /home/user/myapp using uv.
# This produces /home/user/myapp/myapp/myapp.py (the default blank template),
# /home/user/myapp/rxconfig.py, pyproject.toml, and a .venv managed by uv.
RUN mkdir -p /home/user/myapp && \
    cd /home/user/myapp && \
    uv init --name myapp --no-readme --no-workspace . && \
    uv add reflex && \
    uv run reflex init --template blank

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex blank project bootstrapped under /home/user/myapp with uv, Node.js v24, python3, and pytest for evaluating a FastAPI JWT api_transformer task."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf, requests
#   - Node.js v24 (used by Reflex for the frontend compile step)
#   - uv installed via Astral install script and symlinked into /usr/local/bin
#   - /home/user/myapp: blank Reflex project initialized non-interactively with uv
