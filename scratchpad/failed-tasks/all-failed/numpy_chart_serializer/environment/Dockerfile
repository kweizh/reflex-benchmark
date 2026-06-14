FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        psmisc lsof unzip xz-utils build-essential procps && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -sf /root/.local/bin/uv /usr/local/bin/uv && \
    ln -sf /root/.local/bin/uvx /usr/local/bin/uvx && \
    pip3 install --break-system-packages pytest-json-ctrf pytest-xprocess requests && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex task environment for the numpy_chart_serializer task: Ubuntu 24.04, Node.js v24, uv (Astral), system Python with pytest + xprocess + requests for verification."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#     plus psmisc/lsof/procps/unzip/xz-utils/build-essential for process management and dep builds
#   - always required pip3 packages: pytest-json-ctrf
#   - pytest-xprocess and requests for the final-state pytest fixtures
#   - Node.js v24 (Reflex compiles the frontend as a Next.js app)
#   - uv (Astral package manager) installed system-wide via /usr/local/bin symlinks
#   - /home/user: home directory for the task executor
#   - The executor will create /home/user/numpy_chart_serializer themselves
