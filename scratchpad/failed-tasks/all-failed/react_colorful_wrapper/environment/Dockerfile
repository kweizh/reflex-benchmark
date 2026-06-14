FROM ubuntu:24.04

ENV PATH="/root/.local/bin:/usr/local/bin:${PATH}"

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        unzip xz-utils build-essential procps && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    curl -fsSL https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-initialize a blank Reflex project at /home/user/myproject so that
# test_initial_state.py passes before any executor action is taken.
RUN mkdir -p /home/user/myproject && \
    cd /home/user/myproject && \
    uv init --name myproject --no-readme --no-pin-python && \
    uv add reflex && \
    uv run reflex init --template blank && \
    uv run reflex --version

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex (Pynecone) wrapping-react task environment with uv, Node.js v24, and a pre-initialized blank Reflex project at /home/user/myproject."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep unzip xz-utils build-essential procps
#   - Node.js v24 (required by Reflex to compile the Next.js frontend)
#   - uv (Astral) for managing the Python project environment
#   - pip3 packages: pytest-json-ctrf
#   - /home/user/myproject: blank Reflex project initialized via `uv init`, `uv add reflex`, and `reflex init --template blank`
