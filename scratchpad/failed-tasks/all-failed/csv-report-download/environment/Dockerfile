FROM ubuntu:24.04

ARG POCHI_VERSION

# Base tooling, browser libraries for Playwright/Chromium, Node.js, uv, and Python test deps.
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep unzip \
        ffmpeg libxcb-shm0 libx11-xcb1 libx11-6 libxcb1 libxext6 libxrandr2 libxcomposite1 libxcursor1 libxdamage1 libxfixes3 libxi6 libgtk-3-0t64 libpangocairo-1.0-0 libpango-1.0-0 libatk1.0-0t64 libcairo-gobject2 libcairo2 libgdk-pixbuf-2.0-0 libxrender1 libasound2t64 libfreetype6 libfontconfig1 libdbus-1-3 libnss3 libnspr4 libatk-bridge2.0-0t64 libdrm2 libxkbcommon0 libatspi2.0-0t64 libcups2t64 libxshmfence1 libgbm1 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -fsSL https://getpochi.com/install.sh | bash -s ${POCHI_VERSION} && \
    ln -s /root/.pochi/bin/pochi /usr/local/bin/pochi && \
    pip3 install --break-system-packages pytest-json-ctrf uv playwright pytest-xprocess requests && \
    ln -sf /usr/local/bin/uv /usr/bin/uv && \
    python3 -m playwright install chromium && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Scaffold a blank Reflex project managed by uv (frontend :3000, backend :8000).
RUN mkdir -p /home/user/sales_report && \
    cd /home/user/sales_report && \
    uv init --name sales_report --python 3.12 . && \
    uv add "reflex==0.7.14" && \
    uv run reflex init --template blank

# Warm the frontend build cache (installs bun/npm deps) so the first `reflex run` during
# evaluation is fast. Tolerate failure so an occasional export quirk does not break the build.
RUN cd /home/user/sales_report && \
    (uv run reflex export --frontend-only --no-zip --loglevel info || true)

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex (0.7.14) task environment: uv-managed blank app at /home/user/sales_report, Node.js 22, and Playwright/Chromium for browser-based verification."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - unzip + Node.js 22 to support the Reflex frontend/bun toolchain
#   - browser verification deps: Chromium system libs + Playwright (system python) with the chromium browser
#   - uv (system) + a uv-managed blank Reflex 0.7.14 app scaffolded at /home/user/sales_report
#   - pytest deps for verification: pytest-xprocess, requests, playwright

# Setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
