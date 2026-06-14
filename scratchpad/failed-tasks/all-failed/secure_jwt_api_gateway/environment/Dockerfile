FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        unzip xz-utils build-essential psmisc procps lsof && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        pytest-xprocess \
        requests \
        PyJWT && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex + FastAPI JWT API gateway task environment with uv, Node.js v24, and PyJWT/requests/xprocess for final-state verification."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: unzip xz-utils build-essential psmisc procps lsof (needed by uv/reflex/node and process cleanup)
#   - always required pip3 packages: pytest-json-ctrf
#   - pip3 packages for verification: pytest-xprocess, requests, PyJWT
#   - Node.js v24: required by Reflex to build the Next.js frontend
#   - uv (Astral): used by the executor to manage the Reflex Python environment via `uv run`
#   - /home/user: working directory; the executor creates /home/user/secure_jwt_api_gateway
