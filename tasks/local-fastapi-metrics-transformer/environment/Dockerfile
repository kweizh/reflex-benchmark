FROM ubuntu:24.04

ARG POCHI_VERSION

# Base tooling, Node.js (for the Reflex frontend build), uv, Pochi CLI, and the
# Python packages used by the initial/final state tests (run by the system python3).
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        unzip build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    curl -fsSL https://getpochi.com/install.sh | bash -s ${POCHI_VERSION} && \
    ln -s /root/.pochi/bin/pochi /usr/local/bin/pochi && \
    pip3 install --break-system-packages pytest-json-ctrf requests pytest-xprocess && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-initialize the Reflex project with the blank template so that reflex, the
# bun runtime, and the frontend node dependencies are downloaded/cached at build
# time. The agent implements the metrics app inside this project.
RUN mkdir -p /home/user/metrics_app && \
    cd /home/user/metrics_app && \
    uv init --name metrics_app && \
    uv add reflex && \
    uv run reflex init --template blank && \
    (uv run reflex export --frontend-only --no-zip || true)

WORKDIR /home/user/metrics_app

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex project pre-initialized with the blank template (managed by uv) for building a local FastAPI api_transformer metrics dashboard."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - extra pip3 packages for tests: requests, pytest-xprocess
#   - Node.js v20 for the Reflex/Next.js frontend build
#   - uv (Astral) installed and symlinked to /usr/local/bin for managing the Python env
#   - /home/user/metrics_app: Reflex project pre-initialized with the blank template (reflex added via uv)

# Setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
