FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        build-essential unzip xz-utils && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="/usr/local/bin" sh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex task environment: ubuntu 24.04 with Node.js v24, uv (Astral) for Python env management, and pytest. The agent will create /home/user/audio_app from scratch using uv."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - build toolchain: build-essential unzip xz-utils (needed for some pip wheels and uv tarball extraction)
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v24 (Reflex compiles the frontend with Next.js / npm)
#   - uv (Astral) installed to /usr/local/bin so the agent can use `uv` directly per plan.md
#   - /home/user: working directory; the agent creates /home/user/audio_app inside this directory
