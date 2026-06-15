FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        build-essential unzip procps && \
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
LABEL Description="Reflex evaluation environment: ubuntu:24.04 with system python3, uv (Astral) for managing the Reflex Python project, Node.js v24 for the compiled Next.js frontend, and ripgrep/procps for verifier process management."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: build-essential unzip procps (procps provides pgrep/pkill used by the verifier teardown)
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v24: required by the Reflex frontend (Next.js) build/export pipeline
#   - uv (Astral) installed at /root/.local/bin and symlinked to /usr/local/bin/uv and /usr/local/bin/uvx
#   - Reflex itself is NOT pre-installed: the executor MUST initialize the project under
#     /home/user/myproject using `uv` (e.g. `uv init && uv add reflex && uv run reflex init --template blank`)
#   - /home/user: working area for the executor; the verifier expects the Reflex project at /home/user/myproject
