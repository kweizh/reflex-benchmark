FROM ubuntu:24.04

ARG POCHI_VERSION
ARG AGENT_BROWSER_VERSION=0.27.3-pochi

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep unzip \
        ffmpeg libxcb-shm0 libx11-xcb1 libx11-6 libxcb1 libxext6 libxrandr2 libxcomposite1 libxcursor1 libxdamage1 libxfixes3 libxi6 libgtk-3-0t64 libpangocairo-1.0-0 libpango-1.0-0 libatk1.0-0t64 libcairo-gobject2 libcairo2 libgdk-pixbuf-2.0-0 libxrender1 libasound2t64 libfreetype6 libfontconfig1 libdbus-1-3 libnss3 libnspr4 libatk-bridge2.0-0t64 libdrm2 libxkbcommon0 libatspi2.0-0t64 libcups2t64 libxshmfence1 libgbm1 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
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

# Scaffold a blank Reflex project managed by uv at /home/user/note_app.
# This produces the exact initial state validated by test_initial_state.py:
# an initialized uv project with reflex added and `reflex init --template blank`
# already run. The frontend toolchain (bun + node modules) is pre-warmed so the
# app can start without needing to fetch frontend packages at runtime.
RUN mkdir -p /home/user/note_app && \
    cd /home/user/note_app && \
    uv init --name note_app && \
    uv add reflex && \
    uv run reflex init --template blank && \
    (uv run reflex export --frontend-only --no-zip || true)

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex (uv-managed) blank project for a debounced-autosave note editor, with browser verification tooling."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep (+ unzip)
#   - always required pip3 packages: pytest-json-ctrf
#   - browser verification: pochi-verifier, agent-browser, ffmpeg and X/GTK libs
#   - final-test pip3 packages: requests, pytest-xprocess
#   - Node.js v22 (frontend runtime for Reflex)
#   - uv (Astral) installed and symlinked into /usr/local/bin
#   - /home/user/note_app: blank uv-managed Reflex project (reflex added, `reflex init --template blank` run, frontend pre-warmed)

# Setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
