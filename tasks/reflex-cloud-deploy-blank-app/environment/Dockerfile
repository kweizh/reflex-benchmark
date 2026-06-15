FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        unzip xz-utils build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    curl -fsSL https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex Cloud blank-app deploy task environment: ubuntu:24.04 with python3, uv, node.js v24, pytest, and the Reflex Cloud CLI available via `uv run reflex`."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - additional apt packages: unzip xz-utils build-essential (helpful for uv-managed builds)
#   - always required pip3 packages: pytest-json-ctrf
#   - uv (Astral) installed via the official astral.sh installer; the Reflex CLI is invoked via `uv run reflex`
#     (uv will manage the Reflex Python environment inside the agent's project directory)
#   - Node.js v24 (Reflex frontend requires Node to compile the Next.js bundle during deploy)
#   - /home/user: empty home; the agent scaffolds /home/user/myproject during the task
