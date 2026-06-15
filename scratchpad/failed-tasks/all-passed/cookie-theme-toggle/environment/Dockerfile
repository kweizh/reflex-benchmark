FROM ubuntu:24.04

# Base system + tooling needed for the Reflex task and verification.
# - apt packages: standard required set + `unzip` (for some Reflex tooling) and `procps` (for `pkill` used by tests).
# - Node.js v22 is preinstalled so that `reflex export --frontend-only --no-zip` does not have to download it.
# - uv is installed via the official Astral installer, then exposed on the global PATH.
# - System pip installs the Python deps used by the final-state pytest script.
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        unzip procps build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex task environment (uv + Node.js v22) for the cookie-theme-toggle task."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: unzip, procps (for pkill in tests), build-essential (for any C extensions)
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v22 (used by Reflex to compile/export the frontend)
#   - uv installed to /usr/local/bin/uv (used to manage the Reflex Python environment)
#   - /home/user: empty home directory where the agent will create the Reflex project at /home/user/myproject
