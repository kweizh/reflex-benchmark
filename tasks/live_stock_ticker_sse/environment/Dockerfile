FROM ubuntu:24.04

# Install OS deps, system python, pytest, ripgrep, and uv (for the executor's
# Reflex-managed Python env). Also install the pip packages used by the
# verification tests (requests, pytest-xprocess) under the system python3.
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        psmisc procps unzip xz-utils build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages \
        pytest-json-ctrf \
        requests \
        pytest-xprocess && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Standard user directory layout expected by Harbor.
RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex live_stock_ticker_sse task: Ubuntu 24.04 with uv, Node.js 24, system python3 + requests + pytest-xprocess for backend REST verification of a Reflex background-task ticker."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: psmisc (for fuser), procps (for pkill), unzip xz-utils build-essential (uv build deps)
#   - always required pip3 packages: pytest-json-ctrf
#   - extra pip3 packages: requests, pytest-xprocess (used by tests/test_final_state.py to drive and validate the Reflex backend REST surface)
#   - Node.js v24: required by Reflex's Next.js frontend (the executor will run `uv run reflex init` which downloads the frontend toolchain)
#   - uv: Astral package manager used by the executor per plan.md to manage Reflex's Python environment
#   - /home/user: home directory; the executor will create /home/user/ticker_app as the Reflex project root
