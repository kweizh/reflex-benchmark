FROM ubuntu:24.04

ARG POCHI_VERSION
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:${PATH}"
ENV REFLEX_TELEMETRY_ENABLED=false

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep unzip build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -fsSL https://getpochi.com/install.sh | bash -s ${POCHI_VERSION} && \
    ln -s /root/.pochi/bin/pochi /usr/local/bin/pochi && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages pytest-json-ctrf requests pytest-xprocess && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-initialize a blank Reflex project managed by `uv`, initialize the SQLite
# database/alembic scaffolding, and warm the frontend build (downloads bun and
# installs node_modules into .web) so `uv run reflex run` works offline during
# evaluation. The warm-up dev server runs in the background and is stopped as
# soon as the frontend responds (or after a hard cap), keeping build time low.
RUN mkdir -p /home/user/checkout_app && \
    cd /home/user/checkout_app && \
    uv init --name checkout_app && \
    uv add reflex && \
    uv run reflex init --template blank && \
    uv run reflex db init && \
    bash -c 'uv run reflex run --loglevel info & RPID=$!; for i in $(seq 1 300); do if curl -sf http://127.0.0.1:3000 >/dev/null 2>&1; then break; fi; if ! kill -0 $RPID 2>/dev/null; then break; fi; sleep 1; done; kill $RPID 2>/dev/null; wait $RPID 2>/dev/null; true'

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex (pure-Python full-stack) task environment: uv-managed blank Reflex project pre-initialized at /home/user/checkout_app with SQLite DB and warmed frontend for offline dev-server runs."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: unzip build-essential, Node.js v22 (Reflex frontend toolchain)
#   - always required pip3 packages: pytest-json-ctrf
#   - extra pip3 packages (for tests): requests, pytest-xprocess
#   - uv (Astral) package manager installed to /root/.local/bin and symlinked to /usr/local/bin
#   - /home/user/checkout_app: uv-managed blank Reflex project (reflex installed in the uv env,
#     rxconfig.py + checkout_app/checkout_app.py present, DB initialized, .web frontend warmed)

# Setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
