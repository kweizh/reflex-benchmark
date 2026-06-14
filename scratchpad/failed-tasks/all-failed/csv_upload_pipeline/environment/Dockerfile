FROM ubuntu:24.04

# Base toolchain + browser verification dependencies + Node.js v24 + uv + Python tooling.
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        sqlite3 psmisc procps build-essential \
        ffmpeg libxcb-shm0 libx11-xcb1 libx11-6 libxcb1 libxext6 libxrandr2 libxcomposite1 libxcursor1 libxdamage1 libxfixes3 libxi6 libgtk-3-0t64 libpangocairo-1.0-0 libpango-1.0-0 libatk1.0-0t64 libcairo-gobject2 libcairo2 libgdk-pixbuf-2.0-0 libxrender1 libasound2t64 libfreetype6 libfontconfig1 libdbus-1-3 libnss3 libnspr4 libatk-bridge2.0-0t64 libdrm2 libxkbcommon0 libatspi2.0-0t64 libcups2t64 libxshmfence1 libgbm1 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g agent-browser && \
    agent-browser install && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        pytest-xprocess \
        pochi-verifier && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Standard home for the executor.
RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create an empty workspace for the Reflex app the executor will build.
RUN mkdir -p /home/user/myproject && chmod 0755 /home/user/myproject

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex CSV upload + async processing task. Ubuntu 24.04 with uv, Node.js v24, Playwright/agent-browser, sqlite3 and pochi-verifier preinstalled."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep sqlite3 psmisc procps build-essential + browser-verification libs
#   - Node.js v24 (required by Reflex for the Next.js frontend compilation)
#   - agent-browser (npm) + browser-verification ffmpeg/lib*  (required for pochi-verifier UI checks)
#   - uv (Astral) at /usr/local/bin/uv — used to manage the Reflex Python environment
#   - pip3 packages: pytest-json-ctrf, pytest-xprocess, pochi-verifier
#   - /home/user/myproject: empty Reflex workspace the executor will populate
