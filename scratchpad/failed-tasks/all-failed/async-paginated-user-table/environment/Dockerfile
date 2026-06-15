FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest python3-dev bash ripgrep \
        sqlite3 build-essential unzip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        pytest-xprocess \
        requests && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/myproject

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex async paginated user directory task environment with uv, Node.js v24, and sqlite3."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - sqlite3 CLI for schema inspection in the final-state tests
#   - uv (Astral) installed via the official installer and symlinked into /usr/local/bin so it is on PATH
#   - Node.js v24 (Reflex compiles to a Next.js frontend; required for `reflex run` and `reflex export`)
#   - pytest-xprocess + requests for the live dev-server verification fixture
#   - /home/user/myproject: empty project root that the executor populates with the Reflex app
