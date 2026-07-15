FROM ubuntu:24.04

ARG POCHI_VERSION
ARG AGENT_BROWSER_VERSION=0.27.3-pochi

# Reflex must never prompt during build/run (telemetry consent is interactive otherwise).
ENV REFLEX_TELEMETRY_ENABLED=false

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git unzip build-essential python3 python3-pip python3-pytest python3-dev bash ripgrep \
        ffmpeg libxcb-shm0 libx11-xcb1 libx11-6 libxcb1 libxext6 libxrandr2 libxcomposite1 libxcursor1 libxdamage1 libxfixes3 libxi6 libgtk-3-0t64 libpangocairo-1.0-0 libpango-1.0-0 libatk1.0-0t64 libcairo-gobject2 libcairo2 libgdk-pixbuf-2.0-0 libxrender1 libasound2t64 libfreetype6 libfontconfig1 libdbus-1-3 libnss3 libnspr4 libatk-bridge2.0-0t64 libdrm2 libxkbcommon0 libatspi2.0-0t64 libcups2t64 libxshmfence1 libgbm1 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    curl -fsSL https://getpochi.com/install.sh | bash -s ${POCHI_VERSION} && \
    ln -s /root/.pochi/bin/pochi /usr/local/bin/pochi && \
    curl -fsSL https://github.com/TabbyML/agent-browser/releases/download/v${AGENT_BROWSER_VERSION}/install.sh | bash && \
    ln -s /root/.pochi/bin/agent-browser /usr/local/bin/agent-browser && \
    agent-browser install && \
    pip3 install --break-system-packages pytest-json-ctrf pochi-verifier requests pytest-xprocess && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-scaffold a blank Reflex project managed by uv, install dependencies into a
# project-local virtual environment, and warm up the frontend build (downloads
# bun and the JS toolchain) so the app can be run offline during evaluation.
RUN mkdir -p /home/user/editor && \
    cd /home/user/editor && \
    uv init && \
    uv add reflex && \
    uv run reflex init --template blank && \
    uv run reflex export --frontend-only --no-zip && \
    rm -rf /home/user/editor/.web/_static

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex full-stack Python task environment (uv-managed project at /home/user/editor) with browser verification tooling."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - uv (Astral) for managing the Reflex Python environment
#   - browser verification dependencies: pochi-verifier, agent-browser, ffmpeg, and X/graphics libs
#   - test pip3 packages: requests, pytest-xprocess
#   - /home/user/editor: blank Reflex project scaffolded via `uv run reflex init --template blank`
#     with reflex installed in the project's .venv and the frontend toolchain warmed up

# Setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
