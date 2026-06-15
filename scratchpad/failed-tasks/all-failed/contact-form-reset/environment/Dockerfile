FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        lsof psmisc unzip xz-utils build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex task environment: Ubuntu 24.04 with Node.js v24, uv (Astral) for Python env management, and standard verification tooling. The executor builds a Reflex app under /home/user/myproject."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - extra apt packages: lsof psmisc (for port/process cleanup), unzip xz-utils build-essential (for Reflex/Bun runtime)
#   - Node.js v24 (Reflex compiles a Next.js frontend; Bun is auto-fetched by `reflex init` on demand)
#   - uv (Astral) installed via the official installer and symlinked into /usr/local/bin so it is in PATH for all users
#   - /home/user: project workspace where the executor creates the Reflex app at /home/user/myproject
