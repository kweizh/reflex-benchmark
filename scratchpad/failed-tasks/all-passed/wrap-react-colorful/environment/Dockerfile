FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        build-essential unzip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-initialize an empty Reflex project at /home/user/myproject so the executor
# can focus on wrapping the react-colorful component. Reflex is installed inside
# the uv-managed virtualenv per plan.md (system python3 must remain clean for
# the verifier scripts).
RUN mkdir -p /home/user/myproject && \
    cd /home/user/myproject && \
    uv init --no-readme --no-pin-python && \
    uv add "reflex>=0.6.6" && \
    uv run reflex init --template blank && \
    rm -rf .web

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex environment pre-initialized with a blank project at /home/user/myproject for the wrap-react-colorful task."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v24 for the Reflex frontend build (npm + next.js)
#   - astral uv installed at /usr/local/bin/uv for managing the Reflex env
#   - /home/user/myproject: blank Reflex project initialized with `uv init` + `uv add reflex` + `uv run reflex init --template blank`
