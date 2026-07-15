FROM ubuntu:24.04

ARG POCHI_VERSION
ARG AGENT_BROWSER_VERSION=0.27.3-pochi

# System packages, Node.js, Pochi CLI, agent-browser, uv, and Python test deps.
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        procps psmisc unzip \
        ffmpeg libxcb-shm0 libx11-xcb1 libx11-6 libxcb1 libxext6 libxrandr2 libxcomposite1 libxcursor1 libxdamage1 libxfixes3 libxi6 libgtk-3-0t64 libpangocairo-1.0-0 libpango-1.0-0 libatk1.0-0t64 libcairo-gobject2 libcairo2 libgdk-pixbuf-2.0-0 libxrender1 libasound2t64 libfreetype6 libfontconfig1 libdbus-1-3 libnss3 libnspr4 libatk-bridge2.0-0t64 libdrm2 libxkbcommon0 libatspi2.0-0t64 libcups2t64 libxshmfence1 libgbm1 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -fsSL https://getpochi.com/install.sh | bash -s ${POCHI_VERSION} && \
    ln -s /root/.pochi/bin/pochi /usr/local/bin/pochi && \
    curl -fsSL https://github.com/TabbyML/agent-browser/releases/download/v${AGENT_BROWSER_VERSION}/install.sh | bash && \
    ln -s /root/.pochi/bin/agent-browser /usr/local/bin/agent-browser && \
    agent-browser install && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    pip3 install --break-system-packages pytest-json-ctrf pochi-verifier requests pytest-xprocess && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Reflex should not attempt any telemetry network calls at runtime.
ENV REFLEX_TELEMETRY_ENABLED=false

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create a blank Reflex project at /home/user/shopping_cart and pre-warm the
# frontend build (downloads npm/bun deps now, while the network is available), so
# that `uv run reflex run` starts quickly and offline during evaluation.
RUN mkdir -p /home/user/shopping_cart && \
    cd /home/user/shopping_cart && \
    CI=1 uv init --name shopping_cart && \
    CI=1 uv add reflex && \
    CI=1 uv run reflex init --template blank && \
    CI=1 uv run reflex export --frontend-only --no-zip

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex framework task environment (uv-managed) with a pre-created, pre-warmed blank Reflex project at /home/user/shopping_cart and browser verification tooling."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v22 (frontend toolchain support for Reflex)
#   - uv (Astral) at /usr/local/bin/uv for managing the Reflex Python environment
#   - browser verification dependencies: pochi-verifier, agent-browser, ffmpeg, and more
#   - test deps: requests, pytest-xprocess
#   - /home/user/shopping_cart: pre-created + pre-warmed blank Reflex project (rxconfig.py,
#     shopping_cart/ app package, .venv with reflex installed, compiled .web frontend)

# Setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
