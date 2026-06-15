FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        build-essential procps unzip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    pip3 install --break-system-packages pytest-json-ctrf requests && \
    curl -fsSL https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Create the empty project workspace expected by test_initial_state.py.
RUN mkdir -p /home/user/myproject

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex (Pynecone) task environment with uv, Node.js v24, and Python 3 for building a real-time character/word counter app."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - extra pip3 packages: requests (used by tests/test_final_state.py to hit the dev server)
#   - uv (Astral) installed at /root/.local/bin/uv and symlinked into /usr/local/bin
#   - Node.js v24 (required by Reflex's compiled Next.js frontend)
#   - /home/user/myproject: empty workspace where the Reflex app will be created
